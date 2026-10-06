-- mart_role_market_summary.sql
--
-- Role market summary mart.
--
-- Grain:
--   One row per role_family.
--
-- Metric definitions:
--   job_count:
--     Number of deduplicated canonical job postings in the role family.
--
--   median_salary:
--     Median salary_midpoint among jobs with available salary.
--
--   salary_coverage:
--     Share of canonical job postings in the role family with salary available.
--
--   remote_share:
--     Share of canonical job postings in the role family classified as remote.
--
--   top_skill_name:
--     Skill mentioned by the largest number of canonical job postings in the
--     role family.

{{ config(materialized='table') }}

WITH job_facts AS (

    SELECT *
    FROM {{ ref('fact_job_postings') }}

),

skill_mentions AS (

    SELECT *
    FROM {{ ref('fact_job_skill_mentions') }}

),

role_base AS (

    SELECT
        role_family,

        COUNT(DISTINCT job_id)::integer AS job_count,

        COUNT(DISTINCT job_id) FILTER (
            WHERE salary_parse_status <> 'missing'
        )::integer AS jobs_with_salary,

        COUNT(DISTINCT job_id) FILTER (
            WHERE work_mode = 'remote'
        )::integer AS remote_jobs,

        ROUND(
            COUNT(DISTINCT job_id) FILTER (
                WHERE salary_parse_status <> 'missing'
            )::numeric
            / NULLIF(COUNT(DISTINCT job_id), 0),
            4
        )::numeric AS salary_coverage,

        ROUND(
            COUNT(DISTINCT job_id) FILTER (
                WHERE work_mode = 'remote'
            )::numeric
            / NULLIF(COUNT(DISTINCT job_id), 0),
            4
        )::numeric AS remote_share,

        MIN(first_seen_at)::timestamptz AS first_seen_at,
        MAX(last_seen_at)::timestamptz AS last_seen_at

    FROM job_facts
    GROUP BY role_family

),

role_salary_median AS (

    SELECT
        role_family,

        PERCENTILE_CONT(0.5) WITHIN GROUP (
            ORDER BY salary_midpoint
        )::numeric AS median_salary

    FROM job_facts
    WHERE salary_midpoint IS NOT NULL
    GROUP BY role_family

),

role_skill_counts AS (

    SELECT
        f.role_family,
        s.skill_id,
        s.skill_name,

        COUNT(DISTINCT f.job_id)::integer AS skill_job_count

    FROM job_facts f

    INNER JOIN skill_mentions s
        ON f.job_id = s.job_id

    GROUP BY
        f.role_family,
        s.skill_id,
        s.skill_name

),

ranked_role_skills AS (

    SELECT
        role_family,
        skill_id,
        skill_name,
        skill_job_count,

        ROW_NUMBER() OVER (
            PARTITION BY role_family
            ORDER BY skill_job_count DESC, skill_name ASC
        ) AS skill_rank

    FROM role_skill_counts

),

top_role_skills AS (

    SELECT
        role_family,
        skill_id,
        skill_name,
        skill_job_count
    FROM ranked_role_skills
    WHERE skill_rank = 1

),

final AS (

    SELECT
        rb.role_family::text AS role_family,

        rb.job_count::integer AS job_count,
        rb.jobs_with_salary::integer AS jobs_with_salary,

        sm.median_salary::numeric AS median_salary,

        rb.salary_coverage::numeric AS salary_coverage,

        rb.remote_jobs::integer AS remote_jobs,
        rb.remote_share::numeric AS remote_share,

        trs.skill_id::text AS top_skill_id,
        trs.skill_name::text AS top_skill_name,
        COALESCE(trs.skill_job_count, 0)::integer AS top_skill_job_count,

        ROUND(
            COALESCE(trs.skill_job_count, 0)::numeric
            / NULLIF(rb.job_count, 0),
            4
        )::numeric AS top_skill_share,

        rb.first_seen_at::timestamptz AS first_seen_at,
        rb.last_seen_at::timestamptz AS last_seen_at

    FROM role_base rb

    LEFT JOIN role_salary_median sm
        ON rb.role_family = sm.role_family

    LEFT JOIN top_role_skills trs
        ON rb.role_family = trs.role_family

)

SELECT *
FROM final