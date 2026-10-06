-- stg_ingestion_batches.sql
--
-- Staging model for raw.ingestion_batches.
--
-- Grain:
--   One row per ingestion batch.
--
-- Purpose:
--   Clean and standardize ingestion metadata so downstream models can safely
--   filter only successful batches and join job observations back to batch
--   execution metadata.

WITH source AS (

    SELECT *
    FROM {{ source('raw', 'ingestion_batches') }}

),

renamed AS (

    SELECT
        batch_id,

        TRIM(pipeline_name) AS pipeline_name,
        TRIM(source_name) AS source_name,

        started_at::timestamptz AS batch_started_at,
        finished_at::timestamptz AS batch_finished_at,

        UPPER(TRIM(status)) AS batch_status,

        records_expected::integer AS records_expected,
        records_received::integer AS records_received,
        records_loaded::integer AS records_loaded,
        records_quarantined::integer AS records_quarantined,

        api_requests_made::integer AS api_requests_made,
        api_success_count::integer AS api_success_count,
        api_failure_count::integer AS api_failure_count,
        api_rate_limit_hit::boolean AS api_rate_limit_hit,

        retry_count::integer AS retry_count,
        max_retries::integer AS max_retries,

        last_retry_at::timestamptz AS last_retry_at,
        next_retry_at::timestamptz AS next_retry_at,

        NULLIF(TRIM(failure_type), '') AS failure_type,
        is_retryable::boolean AS is_retryable,
        NULLIF(TRIM(error_message), '') AS error_message,

        created_at::timestamptz AS created_at,
        updated_at::timestamptz AS updated_at

    FROM source

)

SELECT *
FROM renamed