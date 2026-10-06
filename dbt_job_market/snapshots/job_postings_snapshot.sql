-- job_postings_snapshot.sql
--
-- dbt snapshot for historical job posting changes.
--
-- Grain:
--   One historical version per canonical job posting.
--
-- Purpose:
--   Preserve meaningful changes to job postings over time.
--
-- Snapshot strategy:
--   check strategy.
--
-- Tracked changes:
--   - job title
--   - company name
--   - location
--   - redirect URL
--   - description hash
--   - salary fields
--   - category fields
--   - contract fields
--   - source created timestamp
--
-- This creates Slowly Changing Dimension Type 2-style history with:
--   dbt_valid_from
--   dbt_valid_to
--
-- A row with dbt_valid_to IS NULL represents the current version.

{% snapshot job_postings_snapshot %}

{{
    config(
        target_schema=target.schema ~ '_snapshots',
        unique_key='job_id',
        strategy='check',
        check_cols=[
            'job_title',
            'company_name',
            'location_text',
            'redirect_url',
            'description_hash',
            'salary_min',
            'salary_max',
            'salary_is_predicted',
            'category_label',
            'category_tag',
            'contract_time',
            'contract_type',
            'source_created_at'
        ]
    )
}}

WITH canonical_jobs AS (

    SELECT *
    FROM {{ ref('int_job_posting_deduped') }}

),

snapshot_source AS (

    SELECT
        job_id,

        identity_type,
        identity_value,

        latest_source_observation_id,
        latest_api_response_id,
        latest_batch_id,
        latest_query_config_id,

        adzuna_job_id,
        normalized_redirect_url,

        job_title,
        company_name,
        location_text,
        redirect_url,

        -- do not need to store the full description text in the snapshot.
        -- A hash is enough to detect whether the description changed.
        MD5(
            REGEXP_REPLACE(
                LOWER(TRIM(COALESCE(description_text_clean, ''))),
                '\s+',
                ' ',
                'g'
            )
        ) AS description_hash,

        source_created_at,
        latest_collected_at,
        latest_raw_inserted_at,

        first_seen_at,
        last_seen_at,
        observation_count,

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

        latest_record_hash

    FROM canonical_jobs

)

SELECT *
FROM snapshot_source

{% endsnapshot %}