-- assert_int_job_skill_matches_unique_grain.sql
--
-- This test protects the declared grain:
--   one row per job_id x skill_name

SELECT
    job_id,
    skill_name,
    COUNT(*) AS row_count
FROM {{ ref('int_job_skill_matches') }}
GROUP BY
    job_id,
    skill_name
HAVING COUNT(*) > 1