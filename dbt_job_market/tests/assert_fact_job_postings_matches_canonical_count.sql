-- assert_fact_job_postings_matches_canonical_count.sql
--
-- This test ensures the main job fact table preserves the canonical job grain:
-- one row per canonical job.

WITH counts AS (

    SELECT
        (SELECT COUNT(*) FROM {{ ref('int_job_posting_deduped') }}) AS canonical_job_count,
        (SELECT COUNT(*) FROM {{ ref('fact_job_postings') }}) AS fact_job_count

)

SELECT *
FROM counts
WHERE canonical_job_count <> fact_job_count