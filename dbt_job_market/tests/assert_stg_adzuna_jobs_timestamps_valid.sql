-- assert_stg_adzuna_jobs_timestamps_valid.sql
--
-- This test checks that the source-side posting timestamp is not later than
-- the pipeline collection timestamp.
--
-- If source_created_at is missing, the row is allowed. Missing timestamps will
-- be handled by later data quality marts.

SELECT
    source_observation_id,
    source_created_at,
    collected_at
FROM {{ ref('stg_adzuna_jobs') }}
WHERE source_created_at IS NOT NULL
  AND collected_at IS NOT NULL
  AND source_created_at > collected_at