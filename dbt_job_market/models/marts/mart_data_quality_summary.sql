-- mart_data_quality_summary.sql
--
-- Current data quality summary mart.
--
-- Grain:
--   One row representing the current warehouse data quality state.

{{ config(materialized='table') }}

WITH staged_observations AS (

    SELECT COUNT(*)::integer AS staged_observation_count
    FROM {{ ref('stg_adzuna_jobs') }}

),

canonical_jobs AS (

    SELECT COUNT(*)::integer AS canonical_job_count
    FROM {{ ref('fact_job_postings') }}

),

salary AS (

    SELECT
        COUNT(*) FILTER (
            WHERE salary_parse_status <> 'missing'
        )::integer AS jobs_with_salary
    FROM {{ ref('fact_job_postings') }}

),

skill_coverage AS (

    SELECT
        COUNT(DISTINCT job_id)::integer AS jobs_with_skill_matches
    FROM {{ ref('fact_job_skill_mentions') }}

),

unknown_roles AS (

    SELECT
        COUNT(*) FILTER (
            WHERE role_family = 'unknown'
        )::integer AS unknown_role_jobs
    FROM {{ ref('fact_job_postings') }}

),

final AS (

    SELECT
        CURRENT_TIMESTAMP::timestamptz AS generated_at,

        s.staged_observation_count,
        c.canonical_job_count,

        GREATEST(
            s.staged_observation_count - c.canonical_job_count,
            0
        )::integer AS duplicate_observation_count,

        ROUND(
            GREATEST(
                s.staged_observation_count - c.canonical_job_count,
                0
            )::numeric
            / NULLIF(s.staged_observation_count, 0),
            4
        )::numeric AS duplicate_percentage,

        sal.jobs_with_salary,

        ROUND(
            sal.jobs_with_salary::numeric
            / NULLIF(c.canonical_job_count, 0),
            4
        )::numeric AS salary_coverage,

        sk.jobs_with_skill_matches,

        ROUND(
            sk.jobs_with_skill_matches::numeric
            / NULLIF(c.canonical_job_count, 0),
            4
        )::numeric AS skill_extraction_coverage,

        ur.unknown_role_jobs,

        ROUND(
            ur.unknown_role_jobs::numeric
            / NULLIF(c.canonical_job_count, 0),
            4
        )::numeric AS unknown_role_share,

        CASE
            WHEN ROUND(
                GREATEST(
                    s.staged_observation_count - c.canonical_job_count,
                    0
                )::numeric
                / NULLIF(s.staged_observation_count, 0),
                4
            ) > 0.75 THEN TRUE
            ELSE FALSE
        END::boolean AS duplicate_rate_warning,

        CASE
            WHEN ROUND(
                sk.jobs_with_skill_matches::numeric
                / NULLIF(c.canonical_job_count, 0),
                4
            ) < 0.25 THEN TRUE
            ELSE FALSE
        END::boolean AS low_skill_extraction_warning,

        CASE
            WHEN ROUND(
                ur.unknown_role_jobs::numeric
                / NULLIF(c.canonical_job_count, 0),
                4
            ) > 0.50 THEN TRUE
            ELSE FALSE
        END::boolean AS high_unknown_role_warning

    FROM staged_observations s

    CROSS JOIN canonical_jobs c
    CROSS JOIN salary sal
    CROSS JOIN skill_coverage sk
    CROSS JOIN unknown_roles ur

)

SELECT *
FROM final