-- assert_mart_company_hiring_summary_share_bounds.sql
--
-- salary_coverage and remote_share must be between 0 and 1.

SELECT
    company_id,
    salary_coverage,
    remote_share
FROM {{ ref('mart_company_hiring_summary') }}
WHERE salary_coverage < 0
   OR salary_coverage > 1
   OR remote_share < 0
   OR remote_share > 1