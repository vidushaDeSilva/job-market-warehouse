-- mart_api_request_summary.sql
--
-- API request observability mart.
--
-- Grain:
--   One row per ingestion batch.

{{ config(materialized='table') }}

WITH batches AS (

    SELECT *
    FROM {{ ref('stg_ingestion_batches') }}

),

api_responses AS (

    SELECT *
    FROM {{ ref('stg_adzuna_api_responses') }}

),

response_summary AS (

    SELECT
        batch_id,

        COUNT(*)::integer AS stored_api_response_count,

        COUNT(*) FILTER (
            WHERE response_status_group = '2xx'
        )::integer AS stored_2xx_response_count,

        COUNT(*) FILTER (
            WHERE response_status_group = '4xx'
        )::integer AS stored_4xx_response_count,

        COUNT(*) FILTER (
            WHERE response_status_group = '5xx'
        )::integer AS stored_5xx_response_count,

        SUM(records_returned)::integer AS total_records_returned_from_responses,

        ROUND(AVG(records_returned), 2)::numeric AS avg_records_per_response,

        MIN(response_received_at)::timestamptz AS first_response_at,
        MAX(response_received_at)::timestamptz AS last_response_at

    FROM api_responses
    GROUP BY batch_id

),

final AS (

    SELECT
        b.batch_id,
        b.source_name,

        b.batch_started_at::date AS request_date,
        b.batch_started_at,
        b.batch_finished_at,
        b.batch_status,

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

        COALESCE(r.stored_api_response_count, 0)::integer AS stored_api_response_count,
        COALESCE(r.stored_2xx_response_count, 0)::integer AS stored_2xx_response_count,
        COALESCE(r.stored_4xx_response_count, 0)::integer AS stored_4xx_response_count,
        COALESCE(r.stored_5xx_response_count, 0)::integer AS stored_5xx_response_count,

        COALESCE(r.total_records_returned_from_responses, 0)::integer
            AS total_records_returned_from_responses,

        r.avg_records_per_response,

        r.first_response_at,
        r.last_response_at,

        CASE
            WHEN b.api_rate_limit_hit = TRUE THEN TRUE
            WHEN b.api_failure_count > 0 THEN TRUE
            ELSE FALSE
        END::boolean AS api_warning

    FROM batches b

    LEFT JOIN response_summary r
        ON b.batch_id = r.batch_id

)

SELECT *
FROM final