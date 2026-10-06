-- assert_int_job_skill_matches_active_seed_only.sql
--
-- This test fails if int_job_skill_matches contains a skill that does not
-- have at least one active alias in the skill dictionary seed.

WITH active_seed_skills AS (

    SELECT DISTINCT
        skill_name
    FROM {{ ref('skill_dictionary') }}
    WHERE LOWER(CAST(is_active AS TEXT)) IN ('true', 't', '1', 'yes', 'y')

),

skill_matches AS (

    SELECT DISTINCT
        skill_name
    FROM {{ ref('int_job_skill_matches') }}

)

SELECT
    m.skill_name
FROM skill_matches m
LEFT JOIN active_seed_skills s
    ON m.skill_name = s.skill_name
WHERE s.skill_name IS NULL