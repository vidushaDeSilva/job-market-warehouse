-- assert_stg_adzuna_jobs_salary_range_valid.sql
--
-- This singular dbt test fails if a staged job has salary_min greater
-- than salary_max.
--
-- The raw table already has a database CHECK constraint, but keeping this
-- dbt test makes the rule visible in dbt docs and dbt test output.

SELECT
    source_observation_id,
    salary_min,
    salary_max
FROM {{ ref('stg_adzuna_jobs') }}
WHERE salary_min IS NOT NULL
  AND salary_max IS NOT NULL
  AND salary_min > salary_max