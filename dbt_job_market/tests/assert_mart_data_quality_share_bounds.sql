-- assert_mart_data_quality_share_bounds.sql

SELECT *
FROM {{ ref('mart_data_quality_summary') }}
WHERE duplicate_percentage < 0
   OR duplicate_percentage > 1
   OR salary_coverage < 0
   OR salary_coverage > 1
   OR skill_extraction_coverage < 0
   OR skill_extraction_coverage > 1
   OR unknown_role_share < 0
   OR unknown_role_share > 1