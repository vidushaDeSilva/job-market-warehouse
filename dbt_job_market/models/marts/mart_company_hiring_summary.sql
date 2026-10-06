-- mart_company_hiring_summary.sql
--
-- Company hiring summary mart.
--
-- Grain:
--   One row per company_id.
--
-- Metric definitions:
--   job_count:
--     Number of deduplicated canonical job postings linked to the company.
--
--   data_engineering_jobs:
--     Number of canonical job postings classified as data_engineering.
--
--   remote_jobs:
--     Number of canonical job postings classified as remote.
--
--   salary_coverage:
--     Share of the company's canonical job postings where salary is available.
--
--   first_seen_at / last_seen_at:
--     Earliest and latest job observation timestamps for the company.

{{ config(materialized='table') }}

WITH job_facts AS (

    SELECT *
    FROM {{ ref('fact_job_postings') }}

),

companies AS (

    SELECT *
    FROM {{ ref('dim_companies') }}

),

summary AS (

    SELECT
        c.company_id::text AS company_id,
        c.company_name::text AS company_name,

        COUNT(DISTINCT f.job_id)::integer AS job_count,

        COUNT(DISTINCT f.job_id) FILTER (
            WHERE f.role_family = 'data_engineering'
        )::integer AS data_engineering_jobs,

        COUNT(DISTINCT f.job_id) FILTER (
            WHERE f.role_family = 'analytics_engineering'
        )::integer AS analytics_engineering_jobs,

        COUNT(DISTINCT f.job_id) FILTER (
            WHERE f.work_mode = 'remote'
        )::integer AS remote_jobs,

        COUNT(DISTINCT f.job_id) FILTER (
            WHERE f.salary_parse_status <> 'missing'
        )::integer AS jobs_with_salary,

        ROUND(
            COUNT(DISTINCT f.job_id) FILTER (
                WHERE f.salary_parse_status <> 'missing'
            )::numeric
            / NULLIF(COUNT(DISTINCT f.job_id), 0),
            4
        )::numeric AS salary_coverage,

        ROUND(
            COUNT(DISTINCT f.job_id) FILTER (
                WHERE f.work_mode = 'remote'
            )::numeric
            / NULLIF(COUNT(DISTINCT f.job_id), 0),
            4
        )::numeric AS remote_share,

        MIN(f.first_seen_at)::timestamptz AS first_seen_at,
        MAX(f.last_seen_at)::timestamptz AS last_seen_at

    FROM companies c

    LEFT JOIN job_facts f
        ON c.company_id = f.company_id

    GROUP BY
        c.company_id,
        c.company_name

)

SELECT *
FROM summary