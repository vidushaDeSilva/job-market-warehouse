-- assert_mart_data_quality_summary_one_row.sql

SELECT
    COUNT(*) AS row_count
FROM {{ ref('mart_data_quality_summary') }}
HAVING COUNT(*) <> 1