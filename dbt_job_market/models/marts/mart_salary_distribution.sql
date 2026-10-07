-- mart_salary_distribution.sql
--
-- Salary distribution mart for the dashboard.
--
-- Grain:
--   One row per salary currency x salary bucket.

{{ config(materialized='table') }}

WITH jobs AS (

    SELECT *
    FROM {{ ref('fact_job_postings') }}
    WHERE salary_midpoint IS NOT NULL
      AND salary_midpoint > 0

),

bucketed AS (

    SELECT
        COALESCE(salary_currency, 'unknown') AS salary_currency,

        CASE
            WHEN salary_midpoint < 30000 THEN 'Under 30k'
            WHEN salary_midpoint >= 30000 AND salary_midpoint < 50000 THEN '30k–50k'
            WHEN salary_midpoint >= 50000 AND salary_midpoint < 70000 THEN '50k–70k'
            WHEN salary_midpoint >= 70000 AND salary_midpoint < 100000 THEN '70k–100k'
            ELSE '100k+'
        END AS salary_bucket,

        CASE
            WHEN salary_midpoint < 30000 THEN 1
            WHEN salary_midpoint >= 30000 AND salary_midpoint < 50000 THEN 2
            WHEN salary_midpoint >= 50000 AND salary_midpoint < 70000 THEN 3
            WHEN salary_midpoint >= 70000 AND salary_midpoint < 100000 THEN 4
            ELSE 5
        END AS salary_bucket_sort,

        job_id

    FROM jobs

),

final AS (

    SELECT
        salary_currency::text AS salary_currency,
        salary_bucket::text AS salary_bucket,
        salary_bucket_sort::integer AS salary_bucket_sort,
        COUNT(DISTINCT job_id)::integer AS job_count

    FROM bucketed

    GROUP BY
        salary_currency,
        salary_bucket,
        salary_bucket_sort

)

SELECT *
FROM final