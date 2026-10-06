-- assert_canonical_jobs_not_more_than_observations.sql
--
-- This test protects the main goal of Sprint 5:
-- canonical job count should not be greater than staged observation count.
--
-- It should normally be less than or equal to the observation count.

WITH counts AS (

    SELECT
        (SELECT COUNT(*) FROM {{ ref('stg_adzuna_jobs') }}) AS observation_count,
        (SELECT COUNT(*) FROM {{ ref('int_job_posting_deduped') }}) AS canonical_job_count

)

SELECT *
FROM counts
WHERE canonical_job_count > observation_count