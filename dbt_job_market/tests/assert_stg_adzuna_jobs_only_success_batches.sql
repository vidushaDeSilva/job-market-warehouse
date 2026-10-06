-- assert_stg_adzuna_jobs_only_success_batches.sql
--
-- This singular dbt test fails if stg_adzuna_jobs contains rows from any
-- batch that is not SUCCESS.
--
-- It directly protects the Sprint 4 rule:
--   staging only reads SUCCESS batches.

SELECT
    j.source_observation_id,
    j.batch_id,
    b.batch_status
FROM {{ ref('stg_adzuna_jobs') }} j
INNER JOIN {{ ref('stg_ingestion_batches') }} b
    ON j.batch_id = b.batch_id
WHERE b.batch_status <> 'SUCCESS'