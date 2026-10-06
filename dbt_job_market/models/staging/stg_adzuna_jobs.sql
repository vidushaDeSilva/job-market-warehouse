-- stg_adzuna_jobs.sql
--
-- Staging model for raw.source_adzuna_jobs.
--
-- Grain:
--   One row per raw Adzuna job observation from a SUCCESS ingestion batch.
--
-- Important:
--   This is still not the canonical deduplicated job table.
--   The same Adzuna job can appear in multiple ingestion batches.
--
-- Main cleaning tasks:
--   - rename columns into consistent analytics names
--   - trim text fields
--   - standardize empty strings to NULL
--   - normalize country and contract fields
--   - strip basic HTML from job descriptions
--   - only include records from SUCCESS ingestion batches

WITH source_jobs AS (

    SELECT *
    FROM {{ source('raw', 'source_adzuna_jobs') }}

),

successful_batches AS (

    SELECT
        batch_id
    FROM {{ ref('stg_ingestion_batches') }}
    WHERE batch_status = 'SUCCESS'

),

cleaned AS (

    SELECT
        -- Technical identifiers
        j.raw_adzuna_job_id AS source_observation_id,
        j.api_response_id,
        j.batch_id,
        j.query_config_id,

        -- Source identifiers
        NULLIF(TRIM(j.adzuna_job_id), '') AS adzuna_job_id,

        -- Job attributes
        NULLIF(TRIM(j.title), '') AS job_title,
        NULLIF(TRIM(j.company_name), '') AS company_name,
        NULLIF(TRIM(j.location_text), '') AS location_text,

        -- Basic HTML stripping and whitespace normalization.
        -- This does not attempt advanced NLP cleaning. That belongs later.
        NULLIF(
            TRIM(
                REGEXP_REPLACE(
                    REGEXP_REPLACE(j.description_text, '<[^>]+>', ' ', 'g'),
                    '\s+',
                    ' ',
                    'g'
                )
            ),
            ''
        ) AS description_text_clean,

        NULLIF(TRIM(j.redirect_url), '') AS redirect_url,

        -- Timestamps
        j.source_created_at::timestamptz AS source_created_at,
        j.collected_at::timestamptz AS collected_at,
        j.created_at::timestamptz AS raw_inserted_at,

        -- Salary fields
        j.salary_min::numeric AS salary_min,
        j.salary_max::numeric AS salary_max,

        CASE
            WHEN LOWER(NULLIF(TRIM(j.salary_is_predicted), '')) IN ('1', 'true', 't', 'yes', 'y') THEN TRUE
            WHEN LOWER(NULLIF(TRIM(j.salary_is_predicted), '')) IN ('0', 'false', 'f', 'no', 'n') THEN FALSE
            ELSE NULL
        END AS salary_is_predicted,

        -- Classification-like source fields
        NULLIF(TRIM(j.category_label), '') AS category_label,
        NULLIF(TRIM(j.category_tag), '') AS category_tag,

        LOWER(NULLIF(TRIM(j.contract_time), '')) AS contract_time,
        LOWER(NULLIF(TRIM(j.contract_type), '')) AS contract_type,

        -- Geography
        j.latitude::numeric AS latitude,
        j.longitude::numeric AS longitude,

        LOWER(NULLIF(TRIM(j.country_code), '')) AS country_code,
        NULLIF(TRIM(j.search_keyword), '') AS search_keyword,
        NULLIF(TRIM(j.search_location), '') AS search_location,

        -- Metadata
        j.record_hash,
        j.raw_payload

    FROM source_jobs j

    INNER JOIN successful_batches b
        ON j.batch_id = b.batch_id

)

SELECT *
FROM cleaned
WHERE job_title IS NOT NULL
  AND company_name IS NOT NULL
  AND description_text_clean IS NOT NULL