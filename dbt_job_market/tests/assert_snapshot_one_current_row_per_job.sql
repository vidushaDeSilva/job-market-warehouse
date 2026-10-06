-- assert_snapshot_one_current_row_per_job.sql
--
-- This test protects the SCD Type 2 snapshot rule:
-- each job should have exactly one current row.
--
-- Current row means:
--   dbt_valid_to IS NULL

SELECT
    job_id,
    COUNT(*) AS current_row_count
FROM {{ ref('job_postings_snapshot') }}
WHERE dbt_valid_to IS NULL
GROUP BY job_id
HAVING COUNT(*) <> 1