-- assert_mart_skill_demand_weekly_share_bounds.sql
--
-- share_of_jobs must be between 0 and 1.

SELECT
    week_start_date,
    skill_id,
    share_of_jobs
FROM {{ ref('mart_skill_demand_weekly') }}
WHERE share_of_jobs < 0
   OR share_of_jobs > 1