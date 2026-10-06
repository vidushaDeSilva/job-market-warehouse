-- mart_ingestion_batch_summary.sql
--
-- Ingestion batch observability mart.
--
-- Grain:
--   One row per ingestion batch.

{{ config(materialized='table') }}

WITH batches AS (

    SELECT *
    FROM {{ ref('stg_ingestion_batches') }}

),

successful_batch_history AS (

    SELECT
        batch_id,

        LAG(records_received) OVER (
            ORDER BY batch_started_at
        ) AS previous_success_records_received

    FROM batches
    WHERE batch_status = 'SUCCESS'

),

final AS (

    SELECT
        b.batch_id,
        b.pipeline_name,
        b.source_name,

        b.batch_started_at,
        b.batch_finished_at,
        b.batch_status,

        EXTRACT(
            EPOCH FROM (b.batch_finished_at - b.batch_started_at)
        )::integer AS batch_duration_seconds,

        b.records_received,
        b.records_loaded,
        b.records_quarantined,

        ROUND(
            b.records_quarantined::numeric
            / NULLIF(b.records_received, 0),
            4
        )::numeric AS quarantine_rate,

        b.api_requests_made,
        b.api_success_count,
        b.api_failure_count,

        ROUND(
            b.api_failure_count::numeric
            / NULLIF(b.api_requests_made, 0),
            4
        )::numeric AS api_failure_rate,

        b.api_rate_limit_hit,

        b.retry_count,
        b.max_retries,

        h.previous_success_records_received::integer AS previous_success_records_received,

        CASE
            WHEN h.previous_success_records_received IS NULL THEN NULL
            WHEN h.previous_success_records_received = 0 THEN NULL
            ELSE ROUND(
                (
                    h.previous_success_records_received - b.records_received
                )::numeric
                / NULLIF(h.previous_success_records_received, 0),
                4
            )
        END::numeric AS records_drop_pct,

        CASE
            WHEN h.previous_success_records_received IS NULL THEN FALSE
            WHEN h.previous_success_records_received = 0 THEN FALSE
            WHEN b.batch_status <> 'SUCCESS' THEN FALSE
            WHEN b.records_received < h.previous_success_records_received * 0.5 THEN TRUE
            ELSE FALSE
        END::boolean AS records_drop_warning,

        CASE
            WHEN b.api_rate_limit_hit = TRUE THEN TRUE
            ELSE FALSE
        END::boolean AS api_429_warning,

        CASE
            WHEN ROUND(
                b.records_quarantined::numeric
                / NULLIF(b.records_received, 0),
                4
            ) > 0.05 THEN TRUE
            ELSE FALSE
        END::boolean AS quarantine_rate_warning,

        b.failure_type,
        b.is_retryable,
        b.error_message

    FROM batches b

    LEFT JOIN successful_batch_history h
        ON b.batch_id = h.batch_id

)

SELECT *
FROM final