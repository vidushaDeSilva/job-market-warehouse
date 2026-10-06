-- assert_snapshot_validity_intervals_valid.sql
--
-- This test fails if any snapshot row has dbt_valid_to earlier than
-- dbt_valid_from.

SELECT
    job_id,
    dbt_valid_from,
    dbt_valid_to
FROM {{ ref('job_postings_snapshot') }}
WHERE dbt_valid_to IS NOT NULL
  AND dbt_valid_to < dbt_valid_from