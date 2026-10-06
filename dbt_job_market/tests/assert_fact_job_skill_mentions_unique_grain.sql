-- assert_fact_job_skill_mentions_unique_grain.sql
--
-- This test protects the grain of fact_job_skill_mentions:
-- one row per job_id x skill_id.

SELECT
    job_id,
    skill_id,
    COUNT(*) AS row_count
FROM {{ ref('fact_job_skill_mentions') }}
GROUP BY
    job_id,
    skill_id
HAVING COUNT(*) > 1