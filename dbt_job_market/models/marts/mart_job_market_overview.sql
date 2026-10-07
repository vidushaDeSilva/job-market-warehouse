-- mart_job_market_overview.sql
--
-- Dashboard overview mart.
--
-- Grain:
--   One row representing the current job market summary.

{{ config(materialized='table') }}

WITH jobs AS (

    SELECT *
    FROM {{ ref('fact_job_postings') }}

),

aggregated AS (

    SELECT
        COUNT(*)::integer AS total_unique_jobs,

        COUNT(*) FILTER (
            WHERE first_seen_at >= DATE_TRUNC('week', CURRENT_DATE)
        )::integer AS jobs_collected_this_week,

        COUNT(*) FILTER (
            WHERE work_mode = 'remote'
        )::integer AS remote_jobs,

        COUNT(*) FILTER (
            WHERE salary_parse_status <> 'missing'
        )::integer AS jobs_with_salary,

        COUNT(DISTINCT company_id)::integer AS unique_companies,

        COUNT(DISTINCT role_family)::integer AS role_family_count,

        MIN(first_seen_at)::timestamptz AS earliest_job_seen_at,
        MAX(latest_collected_at)::timestamptz AS latest_job_collected_at

    FROM jobs

),

final AS (

    SELECT
        CURRENT_TIMESTAMP::timestamptz AS generated_at,

        total_unique_jobs,
        jobs_collected_this_week,

        remote_jobs,

        ROUND(
            remote_jobs::numeric / NULLIF(total_unique_jobs, 0),
            4
        )::numeric AS remote_share,

        jobs_with_salary,

        ROUND(
            jobs_with_salary::numeric / NULLIF(total_unique_jobs, 0),
            4
        )::numeric AS salary_coverage,

        unique_companies,
        role_family_count,

        earliest_job_seen_at,
        latest_job_collected_at

    FROM aggregated

)

SELECT *
FROM final