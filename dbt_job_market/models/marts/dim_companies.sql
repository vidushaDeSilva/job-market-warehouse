-- dim_companies.sql
--
-- Company dimension table.
--
-- Grain:
--   One row per normalized company.
--
-- Purpose:
--   Provides a stable company dimension for job posting analytics.
--   company_id is deterministic and generated from the normalized company name.

{{ config(materialized='table') }}

WITH jobs AS (

    SELECT *
    FROM {{ ref('int_job_posting_deduped') }}

),

normalized AS (

    SELECT
        job_id,
        company_name,
        first_seen_at,
        last_seen_at,
        observation_count,

        NULLIF(
            REGEXP_REPLACE(
                LOWER(TRIM(company_name)),
                '\s+',
                ' ',
                'g'
            ),
            ''
        ) AS company_name_normalized

    FROM jobs

),

grouped AS (

    SELECT
        MD5(
            CONCAT_WS(
                '|',
                'company',
                company_name_normalized
            )
        )::text AS company_id,

        company_name_normalized::text AS company_name_normalized,

        -- Keep a readable display name. If several variants exist, use one of
        -- the latest observed names.
        (ARRAY_AGG(company_name ORDER BY last_seen_at DESC, first_seen_at DESC))[1]::text
            AS company_name,

        MIN(first_seen_at)::timestamptz AS first_seen_at,
        MAX(last_seen_at)::timestamptz AS last_seen_at,

        COUNT(DISTINCT job_id)::integer AS total_job_postings,
        SUM(observation_count)::integer AS total_source_observations

    FROM normalized
    WHERE company_name_normalized IS NOT NULL
    GROUP BY company_name_normalized

)

SELECT *
FROM grouped