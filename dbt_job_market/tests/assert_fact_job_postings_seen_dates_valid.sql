-- assert_fact_job_postings_seen_dates_valid.sql
--
-- A job's first_seen_at should never be after last_seen_at.

SELECT
    job_id,
    first_seen_at,
    last_seen_at
FROM {{ ref('fact_job_postings') }}
WHERE first_seen_at > last_seen_at