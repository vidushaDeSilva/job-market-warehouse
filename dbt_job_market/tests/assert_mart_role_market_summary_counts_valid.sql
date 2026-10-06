-- assert_mart_role_market_summary_counts_valid.sql
--
-- Component counts should not exceed total job_count.

SELECT
    role_family,
    job_count,
    jobs_with_salary,
    remote_jobs,
    top_skill_job_count
FROM {{ ref('mart_role_market_summary') }}
WHERE jobs_with_salary > job_count
   OR remote_jobs > job_count
   OR top_skill_job_count > job_count