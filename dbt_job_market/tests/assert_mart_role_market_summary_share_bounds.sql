-- assert_mart_role_market_summary_share_bounds.sql
--
-- salary_coverage, remote_share, and top_skill_share must be between 0 and 1.

SELECT
    role_family,
    salary_coverage,
    remote_share,
    top_skill_share
FROM {{ ref('mart_role_market_summary') }}
WHERE salary_coverage < 0
   OR salary_coverage > 1
   OR remote_share < 0
   OR remote_share > 1
   OR top_skill_share < 0
   OR top_skill_share > 1