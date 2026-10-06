-- assert_fact_job_postings_salary_range_valid.sql
--
-- This test fails if salary_min is greater than salary_max in the final fact.

SELECT
    job_id,
    salary_min,
    salary_max
FROM {{ ref('fact_job_postings') }}
WHERE salary_min IS NOT NULL
  AND salary_max IS NOT NULL
  AND salary_min > salary_max