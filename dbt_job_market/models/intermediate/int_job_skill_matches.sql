-- int_job_skill_matches.sql
--
-- Skill extraction model.
--
-- Grain:
--   One row per canonical job x normalized skill.
--
-- Purpose:
--   Match job descriptions and job titles against a version-controlled skill
--   dictionary seed.
--
-- Important:
--   The seed can contain multiple aliases per skill. This model collapses those
--   aliases so the output grain remains one row per job x skill.

WITH jobs AS (

    SELECT
        job_id,
        job_title,
        company_name,
        description_text_clean,
        category_label,
        category_tag,

        CONCAT_WS(
            ' ',
            COALESCE(job_title, ''),
            COALESCE(category_label, ''),
            COALESCE(category_tag, ''),
            COALESCE(description_text_clean, '')
        ) AS searchable_text

    FROM {{ ref('int_job_posting_deduped') }}

),

skill_dictionary AS (

    SELECT
        TRIM(skill_name) AS skill_name,
        TRIM(skill_category) AS skill_category,
        TRIM(alias) AS alias,
        TRIM(match_type) AS match_type,
        TRIM(alias_regex) AS alias_regex,

        CASE
            WHEN LOWER(CAST(is_case_sensitive AS TEXT)) IN ('true', 't', '1', 'yes', 'y')
                THEN TRUE
            ELSE FALSE
        END AS is_case_sensitive,

        CASE
            WHEN LOWER(CAST(is_active AS TEXT)) IN ('true', 't', '1', 'yes', 'y')
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

alias_matches AS (

    SELECT
        j.job_id,
        s.skill_name,
        s.skill_category,
        s.alias,
        s.match_type

    FROM jobs j

    CROSS JOIN active_skills s

    WHERE
        CASE
            WHEN s.is_case_sensitive = TRUE
                THEN j.searchable_text ~ s.alias_regex
            ELSE j.searchable_text ~* s.alias_regex
        END

),

collapsed AS (

    SELECT
        MD5(LOWER(TRIM(skill_name))) AS skill_id,
        job_id,
        skill_name,
        skill_category,

        COUNT(*) AS matched_alias_count,

        STRING_AGG(DISTINCT alias, ', ' ORDER BY alias) AS matched_aliases,
        STRING_AGG(DISTINCT match_type, ', ' ORDER BY match_type) AS match_types

    FROM alias_matches
    GROUP BY
        job_id,
        skill_name,
        skill_category

)

SELECT *
FROM collapsed