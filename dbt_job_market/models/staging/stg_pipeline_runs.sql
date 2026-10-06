-- stg_pipeline_runs.sql
--
-- Staging model for ops.pipeline_runs.
--
-- Grain:
--   One row per observed end-to-end pipeline execution.

WITH source AS (

    SELECT *
    FROM {{ source('ops', 'pipeline_runs') }}

),

renamed AS (

    SELECT
        pipeline_run_id,
        TRIM(pipeline_name) AS pipeline_name,

        started_at::timestamptz AS pipeline_started_at,
        finished_at::timestamptz AS pipeline_finished_at,

        UPPER(TRIM(status)) AS pipeline_status,
        UPPER(TRIM(trigger_type)) AS trigger_type,

        ingestion_batch_id,

        NULLIF(TRIM(dbt_invocation_id), '') AS dbt_invocation_id,
        NULLIF(UPPER(TRIM(dbt_status)), '') AS dbt_status,

        COALESCE(tests_passed, 0)::integer AS tests_passed,
        COALESCE(tests_failed, 0)::integer AS tests_failed,

        NULLIF(TRIM(git_sha), '') AS git_sha,
        NULLIF(TRIM(error_message), '') AS error_message,

        created_at::timestamptz AS created_at,
        updated_at::timestamptz AS updated_at

    FROM source

)

SELECT *
FROM renamed