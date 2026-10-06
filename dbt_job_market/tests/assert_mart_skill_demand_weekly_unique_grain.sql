-- assert_mart_skill_demand_weekly_unique_grain.sql
--
-- Protects the grain:
--   one row per week_start_date x skill_id.

SELECT
    week_start_date,
    skill_id,
    COUNT(*) AS row_count
FROM {{ ref('mart_skill_demand_weekly') }}
GROUP BY
    week_start_date,
    skill_id
HAVING COUNT(*) > 1