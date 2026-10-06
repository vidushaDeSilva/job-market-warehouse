-- int_salary_normalized.sql
--
-- Salary normalization model.
--
-- Grain:
--   One row per canonical job.
--
-- Purpose:
--   Preserve Adzuna salary fields while adding transparent parse/status fields.
--
-- Important:
--   We do not silently invent missing salary values. If salary is missing, the
--   status remains "missing". Currency and period are marked with source fields
--   so assumptions are visible.

WITH jobs AS (

    SELECT *
    FROM {{ ref('int_job_posting_deduped') }}

),

normalized AS (

    SELECT
        job_id,

        salary_min,
        salary_max,
        salary_is_predicted,

        CASE
            WHEN salary_min IS NULL AND salary_max IS NULL THEN NULL
            WHEN salary_min IS NOT NULL AND salary_max IS NOT NULL THEN (salary_min + salary_max) / 2.0
            WHEN salary_min IS NOT NULL THEN salary_min
            WHEN salary_max IS NOT NULL THEN salary_max
        END AS salary_midpoint,

        CASE
            WHEN salary_min IS NULL AND salary_max IS NULL THEN 'missing'
            WHEN salary_min IS NOT NULL AND salary_max IS NOT NULL AND salary_min > salary_max THEN 'invalid_range'
            WHEN salary_min IS NOT NULL AND salary_max IS NULL THEN 'partial_min_only'
            WHEN salary_min IS NULL AND salary_max IS NOT NULL THEN 'partial_max_only'
            ELSE 'parsed'
        END AS salary_parse_status,

        -- Adzuna salary fields do not give a separate currency column in our
        -- current raw design. We infer currency from country_code and explicitly
        -- mark the source as country_code_inferred.
        CASE
            WHEN salary_min IS NULL AND salary_max IS NULL THEN NULL
            WHEN country_code = 'gb' THEN 'GBP'
            WHEN country_code = 'us' THEN 'USD'
            WHEN country_code IN ('it', 'de', 'fr', 'es', 'nl', 'ie') THEN 'EUR'
            WHEN country_code = 'ca' THEN 'CAD'
            WHEN country_code = 'au' THEN 'AUD'
            ELSE NULL
        END AS salary_currency,

        CASE
            WHEN salary_min IS NULL AND salary_max IS NULL THEN 'not_available'
            WHEN country_code IN ('gb', 'us', 'it', 'de', 'fr', 'es', 'nl', 'ie', 'ca', 'au')
                THEN 'country_code_inferred'
            ELSE 'unknown'
        END AS salary_currency_source,

        -- Adzuna salary_min/salary_max are treated as annual salary fields for
        -- this project. The source field makes the assumption explicit.
        CASE
            WHEN salary_min IS NULL AND salary_max IS NULL THEN NULL
            ELSE 'annual'
        END AS salary_period,

        CASE
            WHEN salary_min IS NULL AND salary_max IS NULL THEN 'not_available'
            ELSE 'project_assumption_adzuna_salary_fields'
        END AS salary_period_source,

        country_code,
        latest_collected_at

    FROM jobs

)

SELECT *
FROM normalized