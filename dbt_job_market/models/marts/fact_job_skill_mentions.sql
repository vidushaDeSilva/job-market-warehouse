-- fact_job_skill_mentions.sql
--
-- Job-skill bridge/fact table.
--
-- Grain:
--   One row per canonical job x skill.
--
-- Purpose:
--   Represents the many-to-many relationship between job postings and skills.

{{ config(materialized='table') }}

WITH skill_matches AS (

    SELECT *
    FROM {{ ref('int_job_skill_matches') }}

),

skills AS (

    SELECT *
    FROM {{ ref('dim_skills') }}

),

job_postings AS (

    SELECT *
    FROM {{ ref('fact_job_postings') }}

),

joined AS (

    SELECT
        MD5(
            CONCAT_WS(
                '|',
                'job_skill',
                m.job_id,
                s.skill_id
            )
        )::text AS job_skill_id,

        m.job_id::text AS job_id,
        s.skill_id::text AS skill_id,

        m.skill_name::text AS skill_name,
        m.skill_category::text AS skill_category,

        m.matched_alias_count::integer AS matched_alias_count,
        m.matched_aliases::text AS matched_aliases,
        m.match_types::text AS match_types

    FROM skill_matches m

    INNER JOIN skills s
        ON m.skill_name = s.skill_name

    INNER JOIN job_postings j
        ON m.job_id = j.job_id

)

SELECT *
FROM joined