-- assert_int_job_posting_seen_dates_valid.sql
--
-- This test fails if the first observed timestamp is after the latest observed
-- timestamp for a canonical job.

SELECT
    job_id,
    first_seen_at,
    last_seen_at
FROM {{ ref('int_job_posting_deduped') }}
WHERE first_seen_at > last_seen_at