-- dim_skills.sql
--
-- Skill dimension table.
--
-- Grain:
--   One row per normalized skill.
--
-- Purpose:
--   Provides stable skill identifiers for the job-skill bridge/fact table.
--   The source is the dbt seed skill_dictionary, not raw Adzuna data.

{{ config(materialized='table') }}

WITH skill_dictionary AS (

    SELECT
        TRIM(skill_name) AS skill_name,
        TRIM(skill_category) AS skill_category,
        TRIM(alias) AS alias,

        CASE
            WHEN LOWER(CAST(is_active AS text)) IN ('true', 't', '1', 'yes', 'y')
                THEN TRUE
            ELSE FALSE
        END AS is_active

    FROM {{ ref('skill_dictionary') }}

),

active_skills AS (

    SELECT *
    FROM skill_dictionary
    WHERE is_active = TRUE

),

grouped AS (

    SELECT
        MD5(LOWER(TRIM(skill_name)))::text AS skill_id,

        skill_name::text AS skill_name,

        -- A skill should normally have one category. MIN is used as a safe
        -- deterministic choice if the seed accidentally contains variation.
        MIN(skill_category)::text AS skill_category,

        COUNT(DISTINCT alias)::integer AS active_alias_count,

        TRUE::boolean AS is_active

    FROM active_skills
    GROUP BY skill_name

)

SELECT *
FROM grouped