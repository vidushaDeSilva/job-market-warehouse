-- assert_int_job_posting_latest_matches_last_seen.sql
--
-- This test ensures that the selected latest observation really represents
-- the most recent observed version of the canonical job.

SELECT
    job_id,
    latest_collected_at,
    last_seen_at
FROM {{ ref('int_job_posting_deduped') }}
WHERE latest_collected_at <> last_seen_at