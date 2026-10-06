-- assert_int_job_posting_observation_count_positive.sql
--
-- This test fails if a canonical job has no source observations.
-- Every canonical job must come from at least one staged observation.

SELECT
    job_id,
    observation_count
FROM {{ ref('int_job_posting_deduped') }}
WHERE observation_count < 1