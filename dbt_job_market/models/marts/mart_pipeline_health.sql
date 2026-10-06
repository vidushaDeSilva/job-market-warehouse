-- mart_pipeline_health.sql
--
-- Current pipeline health mart.
--
-- Grain:
--   One row representing the current operational health state.
--
-- Main warning rules:
--   - no successful collection for more than expected interval
--   - latest successful records dropped by more than 50%
--   - API 429 encountered
--   - dbt tests failed
--   - duplicate rate unusually high

{{ config(materialized='table') }}

WITH settings AS (

    SELECT
        24::integer AS expected_collection_interval_hours,
        26::integer AS stale_after_hours

),

pipeline_runs AS (

    SELECT *
    FROM {{ ref('stg_pipeline_runs') }}

),

latest_pipeline_run AS (

    SELECT *
    FROM pipeline_runs
    ORDER BY pipeline_started_at DESC
    LIMIT 1

),

last_successful_pipeline_run AS (

    SELECT
        MAX(pipeline_finished_at)::timestamptz AS last_successful_pipeline_finished_at
    FROM pipeline_runs
    WHERE pipeline_status = 'SUCCESS'

),

batch_summary AS (

    SELECT *
    FROM {{ ref('mart_ingestion_batch_summary') }}

),

latest_batch AS (

    SELECT *
    FROM batch_summary
    ORDER BY batch_started_at DESC
    LIMIT 1

),

last_successful_ingestion AS (

    SELECT
        MAX(batch_finished_at)::timestamptz AS last_successful_ingestion_finished_at
    FROM batch_summary
    WHERE batch_status = 'SUCCESS'

),

data_quality AS (

    SELECT *
    FROM {{ ref('mart_data_quality_summary') }}
    LIMIT 1

),

final AS (

    SELECT
        CURRENT_TIMESTAMP::timestamptz AS health_checked_at,

        s.expected_collection_interval_hours,
        s.stale_after_hours,

        lpr.pipeline_run_id AS latest_pipeline_run_id,
        lpr.pipeline_status AS latest_pipeline_status,
        lpr.pipeline_started_at AS latest_pipeline_started_at,
        lpr.pipeline_finished_at AS latest_pipeline_finished_at,
        lpr.tests_passed,
        lpr.tests_failed,
        lpr.dbt_invocation_id,
        lpr.git_sha,

        lspr.last_successful_pipeline_finished_at,

        lb.batch_id AS latest_ingestion_batch_id,
        lb.batch_status AS latest_ingestion_batch_status,
        lb.batch_started_at AS latest_ingestion_started_at,
        lb.batch_finished_at AS latest_ingestion_finished_at,
        lb.records_received AS latest_records_received,
        lb.records_loaded AS latest_records_loaded,
        lb.records_quarantined AS latest_records_quarantined,
        lb.api_requests_made AS latest_api_requests_made,
        lb.api_failure_count AS latest_api_failure_count,
        lb.api_failure_rate AS latest_api_failure_rate,
        lb.api_rate_limit_hit AS latest_api_rate_limit_hit,

        lsi.last_successful_ingestion_finished_at,

        EXTRACT(
            EPOCH FROM (
                CURRENT_TIMESTAMP - lsi.last_successful_ingestion_finished_at
            )
        ) / 3600.0 AS hours_since_last_successful_ingestion,

        dq.duplicate_percentage,
        dq.salary_coverage,
        dq.skill_extraction_coverage,
        dq.unknown_role_share,

        CASE
            WHEN lsi.last_successful_ingestion_finished_at IS NULL THEN TRUE
            WHEN CURRENT_TIMESTAMP - lsi.last_successful_ingestion_finished_at
                 > (s.stale_after_hours || ' hours')::interval THEN TRUE
            ELSE FALSE
        END::boolean AS stale_collection_warning,

        COALESCE(lb.records_drop_warning, FALSE)::boolean AS records_drop_warning,

        COALESCE(lb.api_429_warning, FALSE)::boolean AS api_429_warning,

        CASE
            WHEN COALESCE(lpr.tests_failed, 0) > 0 THEN TRUE
            ELSE FALSE
        END::boolean AS dbt_test_failure_warning,

        COALESCE(dq.duplicate_rate_warning, FALSE)::boolean AS duplicate_rate_warning,

        COALESCE(dq.low_skill_extraction_warning, FALSE)::boolean
            AS low_skill_extraction_warning,

        COALESCE(dq.high_unknown_role_warning, FALSE)::boolean
            AS high_unknown_role_warning,

        CASE
            WHEN lsi.last_successful_ingestion_finished_at IS NULL THEN 'critical'
            WHEN lpr.pipeline_status = 'FAILED' THEN 'critical'
            WHEN CURRENT_TIMESTAMP - lsi.last_successful_ingestion_finished_at
                 > (s.stale_after_hours || ' hours')::interval THEN 'warning'
            WHEN COALESCE(lb.records_drop_warning, FALSE) = TRUE THEN 'warning'
            WHEN COALESCE(lb.api_429_warning, FALSE) = TRUE THEN 'warning'
            WHEN COALESCE(lpr.tests_failed, 0) > 0 THEN 'warning'
            WHEN COALESCE(dq.duplicate_rate_warning, FALSE) = TRUE THEN 'warning'
            WHEN COALESCE(dq.low_skill_extraction_warning, FALSE) = TRUE THEN 'warning'
            WHEN COALESCE(dq.high_unknown_role_warning, FALSE) = TRUE THEN 'warning'
            ELSE 'healthy'
        END::text AS pipeline_health_status

    FROM settings s

    LEFT JOIN latest_pipeline_run lpr
        ON TRUE

    LEFT JOIN last_successful_pipeline_run lspr
        ON TRUE

    LEFT JOIN latest_batch lb
        ON TRUE

    LEFT JOIN last_successful_ingestion lsi
        ON TRUE

    LEFT JOIN data_quality dq
        ON TRUE

)

SELECT *
FROM final