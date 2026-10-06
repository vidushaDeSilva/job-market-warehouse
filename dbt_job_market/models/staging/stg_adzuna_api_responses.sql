-- stg_adzuna_api_responses.sql
--
-- Staging model for raw.adzuna_api_responses.
--
-- Grain:
--   One row per Adzuna API response/page.

WITH source AS (

    SELECT *
    FROM {{ source('raw', 'adzuna_api_responses') }}

),

renamed AS (

    SELECT
        api_response_id,
        batch_id,
        query_config_id,

        TRIM(source_name) AS source_name,
        LOWER(TRIM(country_code)) AS country_code,
        NULLIF(TRIM(keyword), '') AS keyword,
        NULLIF(TRIM(location), '') AS location,

        page_number::integer AS page_number,
        results_per_page::integer AS results_per_page,

        request_url_hash,
        request_params_json,

        response_status_code::integer AS response_status_code,
        response_received_at::timestamptz AS response_received_at,

        records_returned::integer AS records_returned,
        total_count::integer AS total_count,

        raw_response_json,
        created_at::timestamptz AS created_at,

        CASE
            WHEN response_status_code BETWEEN 200 AND 299 THEN TRUE
            ELSE FALSE
        END AS request_succeeded,

        CASE
            WHEN response_status_code BETWEEN 200 AND 299 THEN '2xx'
            WHEN response_status_code BETWEEN 300 AND 399 THEN '3xx'
            WHEN response_status_code BETWEEN 400 AND 499 THEN '4xx'
            WHEN response_status_code BETWEEN 500 AND 599 THEN '5xx'
            ELSE 'unknown'
        END AS response_status_group

    FROM source

)

SELECT *
FROM renamed