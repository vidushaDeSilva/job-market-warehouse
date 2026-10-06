-- assert_int_salary_normalized_range_valid.sql
--
-- This test fails if salary_min is greater than salary_max.
-- Even though raw has a database constraint, this dbt test keeps the rule
-- visible in dbt test output and docs.

SELECT
    job_id,
    salary_min,
    salary_max
FROM {{ ref('int_salary_normalized') }}
WHERE salary_min IS NOT NULL
  AND salary_max IS NOT NULL
  AND salary_min > salary_max