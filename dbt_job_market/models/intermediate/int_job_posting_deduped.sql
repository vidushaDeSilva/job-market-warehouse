-- int_job_posting_deduped.sql
--
-- Canonical deduplicated job posting model.
--
-- Grain:
--   One row per canonical job posting.
--
-- Purpose:
--   Convert repeated Adzuna job observations into stable job entities.
--
-- Identity hierarchy:
--   1. Adzuna job ID
--   2. Normalized redirect URL
--   3. Fallback natural-key hash
--
-- Important:
--   row_number() is used only to select the latest observation inside each
--   canonical job group. It is NOT used to generate job_id.

WITH observations AS (

    SELECT *
    FROM {{ ref('stg_adzuna_jobs') }}

),

normalized AS (

    SELECT
        source_observation_id,
        api_response_id,
        batch_id,
        query_config_id,

        -- Original cleaned fields from staging.
        adzuna_job_id,
        job_title,
        company_name,
        location_text,
        description_text_clean,
        redirect_url,

        source_created_at,
        collected_at,
        raw_inserted_at,

        salary_min,
        salary_max,
        salary_is_predicted,

        category_label,
        category_tag,
        contract_time,
        contract_type,

        latitude,
        longitude,

        country_code,
        search_keyword,
        search_location,

        record_hash,
        raw_payload,

        -- Normalized identity candidates.
        NULLIF(LOWER(TRIM(adzuna_job_id)), '') AS normalized_adzuna_job_id,

        CASE
            WHEN redirect_url IS NOT NULL THEN
                NULLIF(
                    REGEXP_REPLACE(
                        LOWER(TRIM(SPLIT_PART(redirect_url, '?', 1))),
                        '/+$',
                        ''
                    ),
                    ''
                )
            ELSE NULL
        END AS normalized_redirect_url,

        NULLIF(
            REGEXP_REPLACE(LOWER(TRIM(job_title)), '\s+', ' ', 'g'),
            ''
        ) AS normalized_job_title,

        NULLIF(
            REGEXP_REPLACE(LOWER(TRIM(company_name)), '\s+', ' ', 'g'),
            ''
        ) AS normalized_company_name,

        NULLIF(
            REGEXP_REPLACE(LOWER(TRIM(COALESCE(location_text, ''))), '\s+', ' ', 'g'),
            ''
        ) AS normalized_location_text,

        MD5(
            REGEXP_REPLACE(
                LOWER(TRIM(COALESCE(description_text_clean, ''))),
                '\s+',
                ' ',
                'g'
            )
        ) AS description_hash

    FROM observations

),

identity_candidates AS (

    SELECT
        *,

        CASE
            WHEN normalized_adzuna_job_id IS NOT NULL THEN 'adzuna_job_id'
            WHEN normalized_redirect_url IS NOT NULL THEN 'normalized_url'
            ELSE 'natural_key_hash'
        END AS identity_type,

        CASE
            WHEN normalized_adzuna_job_id IS NOT NULL THEN normalized_adzuna_job_id
            WHEN normalized_redirect_url IS NOT NULL THEN normalized_redirect_url
            ELSE MD5(
                CONCAT_WS(
                    '|',
                    COALESCE(normalized_company_name, ''),
                    COALESCE(normalized_job_title, ''),
                    COALESCE(normalized_location_text, ''),
                    COALESCE(description_hash, '')
                )
            )
        END AS identity_value

    FROM normalized

),

keyed AS (

    SELECT
        *,

        -- Stable deterministic job ID.
        --
        -- Including identity_type prevents accidental collisions between
        -- different identity strategies.
        MD5(
            CONCAT_WS(
                '|',
                'job',
                identity_type,
                identity_value
            )
        ) AS job_id

    FROM identity_candidates

),

with_observation_stats AS (

    SELECT
        *,

        MIN(collected_at) OVER (
            PARTITION BY job_id
        ) AS first_seen_at,

        MAX(collected_at) OVER (
            PARTITION BY job_id
        ) AS last_seen_at,

        COUNT(*) OVER (
            PARTITION BY job_id
        ) AS observation_count

    FROM keyed

),

ranked AS (

    SELECT
        *,

        ROW_NUMBER() OVER (
            PARTITION BY job_id
            ORDER BY
                collected_at DESC NULLS LAST,
                source_created_at DESC NULLS LAST,
                raw_inserted_at DESC NULLS LAST,
                source_observation_id DESC
        ) AS latest_observation_rank

    FROM with_observation_stats

),

deduped AS (

    SELECT
        job_id,

        identity_type,
        identity_value,

        -- Latest selected observation.
        source_observation_id AS latest_source_observation_id,
        api_response_id AS latest_api_response_id,
        batch_id AS latest_batch_id,
        query_config_id AS latest_query_config_id,

        -- Source identifiers.
        adzuna_job_id,
        normalized_redirect_url,

        -- Latest job attributes.
        job_title,
        company_name,
        location_text,
        description_text_clean,
        redirect_url,

        source_created_at,
        collected_at AS latest_collected_at,
        raw_inserted_at AS latest_raw_inserted_at,

        -- Observation history summary.
        first_seen_at,
        last_seen_at,
        observation_count,

        -- Latest salary/source classification fields.
        salary_min,
        salary_max,
        salary_is_predicted,

        category_label,
        category_tag,
        contract_time,
        contract_type,

        latitude,
        longitude,

        country_code,
        search_keyword,
        search_location,

        record_hash AS latest_record_hash,

        raw_payload AS latest_raw_payload

    FROM ranked
    WHERE latest_observation_rank = 1

)

SELECT *
FROM deduped