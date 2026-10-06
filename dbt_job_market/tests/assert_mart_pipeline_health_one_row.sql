-- assert_mart_pipeline_health_one_row.sql

SELECT
    COUNT(*) AS row_count
FROM {{ ref('mart_pipeline_health') }}
HAVING COUNT(*) <> 1