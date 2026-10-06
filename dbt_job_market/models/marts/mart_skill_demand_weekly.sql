-- mart_skill_demand_weekly.sql
--
-- Weekly skill demand mart.
--
-- Grain:
--   One row per week_start_date x skill_id.
--
-- Metric definitions:
--   week_start_date:
--     Monday-starting week based on fact_job_postings.first_seen_at.
--
--   unique_job_count:
--     Number of deduplicated canonical job postings first seen in that week
--     that mention the skill.
--
--   total_unique_jobs_in_week:
--     Number of deduplicated canonical job postings first seen in that week,
--     regardless of whether they mention this specific skill.
--
--   share_of_jobs:
--     unique_job_count / total_unique_jobs_in_week.
--
-- Important:
--   A job can mention multiple skills, so shares across skills do not sum to 1.

{{ config(materialized='table') }}

WITH job_weeks AS (

    SELECT
        job_id,
        DATE_TRUNC('week', first_seen_at)::date AS week_start_date
    FROM {{ ref('fact_job_postings') }}
    WHERE first_seen_at IS NOT NULL

),

weekly_totals AS (

    SELECT
        week_start_date,
        COUNT(DISTINCT job_id)::integer AS total_unique_jobs_in_week
    FROM job_weeks
    GROUP BY week_start_date

),

skill_jobs AS (

    SELECT
        jw.week_start_date,
        s.skill_id,
        ds.skill_name,
        ds.skill_category,

        COUNT(DISTINCT jw.job_id)::integer AS unique_job_count

    FROM job_weeks jw

    INNER JOIN {{ ref('fact_job_skill_mentions') }} s
        ON jw.job_id = s.job_id

    INNER JOIN {{ ref('dim_skills') }} ds
        ON s.skill_id = ds.skill_id

    GROUP BY
        jw.week_start_date,
        s.skill_id,
        ds.skill_name,
        ds.skill_category

),

final AS (

    SELECT
        sj.week_start_date::date AS week_start_date,
        sj.skill_id::text AS skill_id,
        sj.skill_name::text AS skill_name,
        sj.skill_category::text AS skill_category,

        sj.unique_job_count::integer AS unique_job_count,
        wt.total_unique_jobs_in_week::integer AS total_unique_jobs_in_week,

        ROUND(
            sj.unique_job_count::numeric
            / NULLIF(wt.total_unique_jobs_in_week, 0),
            4
        )::numeric AS share_of_jobs

    FROM skill_jobs sj

    INNER JOIN weekly_totals wt
        ON sj.week_start_date = wt.week_start_date

)

SELECT *
FROM final