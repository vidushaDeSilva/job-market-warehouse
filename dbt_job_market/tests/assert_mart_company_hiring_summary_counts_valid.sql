-- assert_mart_company_hiring_summary_counts_valid.sql
--
-- Component counts should not exceed total job_count.

SELECT
    company_id,
    job_count,
    data_engineering_jobs,
    analytics_engineering_jobs,
    remote_jobs,
    jobs_with_salary
FROM {{ ref('mart_company_hiring_summary') }}
WHERE data_engineering_jobs > job_count
   OR analytics_engineering_jobs > job_count
   OR remote_jobs > job_count
   OR jobs_with_salary > job_count