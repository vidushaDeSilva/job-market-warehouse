-- assert_mart_ingestion_batch_summary_rate_bounds.sql

SELECT *
FROM {{ ref('mart_ingestion_batch_summary') }}
WHERE quarantine_rate < 0
   OR quarantine_rate > 1
   OR api_failure_rate < 0
   OR api_failure_rate > 1
   OR records_drop_pct < -1