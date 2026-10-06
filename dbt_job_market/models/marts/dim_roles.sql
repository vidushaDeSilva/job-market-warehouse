-- dim_roles.sql
--
-- Role dimension table.
--
-- Grain:
--   One row per role_family x seniority_level x work_mode combination.
--
-- Purpose:
--   Provides standardized role categories for fact_job_postings.

{{ config(materialized='table') }}

WITH role_classification AS (

    SELECT *
    FROM {{ ref('int_role_classification') }}

),

grouped AS (

    SELECT
        MD5(
            CONCAT_WS(
                '|',
                'role',
                role_family,
                seniority_level,
                work_mode
            )
        )::text AS role_id,

        role_family::text AS role_family,
        seniority_level::text AS seniority_level,
        work_mode::text AS work_mode,

        CONCAT(
            role_family,
            ' / ',
            seniority_level,
            ' / ',
            work_mode
        )::text AS role_label,

        COUNT(DISTINCT job_id)::integer AS jobs_observed

    FROM role_classification
    GROUP BY
        role_family,
        seniority_level,
        work_mode

)

SELECT *
FROM grouped