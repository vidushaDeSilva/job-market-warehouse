-- fact_job_postings.sql
--
-- Main job posting fact table.
--
-- Grain:
--   One row per canonical job posting.
--
-- Purpose:
--   Combines canonical jobs, salary normalization, role classification, and
--   dimension keys into an analytics-ready fact table.

{{ config(materialized='table') }}

WITH jobs AS (

    SELECT *
    FROM {{ ref('int_job_posting_deduped') }}

),

salary AS (

    SELECT *
    FROM {{ ref('int_salary_normalized') }}

),

roles AS (

    SELECT *
    FROM {{ ref('int_role_classification') }}

),

prepared AS (

    SELECT
        j.job_id,

        NULLIF(
            REGEXP_REPLACE(
                LOWER(TRIM(j.company_name)),
                '\s+',
                ' ',
                'g'
            ),
            ''
        ) AS company_name_normalized,

        r.role_family,
        r.seniority_level,
        r.work_mode,
        r.classification_rule,
        r.classification_confidence,

        j.latest_source_observation_id,
        j.adzuna_job_id,
        j.job_title,
        j.company_name,
        j.location_text,
        j.redirect_url,

        j.source_created_at,
        j.first_seen_at,
        j.last_seen_at,
        j.latest_collected_at,
        j.observation_count,

        s.salary_min,
        s.salary_max,
        s.salary_midpoint,
        s.salary_currency,
        s.salary_period,
        s.salary_parse_status,
        j.salary_is_predicted,

        j.country_code,
        j.search_keyword,
        j.search_location,

        j.category_label,
        j.category_tag,
        j.contract_time,
        j.contract_type,

        j.latitude,
        j.longitude,

        j.latest_record_hash

    FROM jobs j

    LEFT JOIN salary s
        ON j.job_id = s.job_id

    LEFT JOIN roles r
        ON j.job_id = r.job_id

),

with_dimension_keys AS (

    SELECT
        p.job_id::text AS job_id,

        c.company_id::text AS company_id,
        d.role_id::text AS role_id,

        p.latest_source_observation_id,
        p.adzuna_job_id::text AS adzuna_job_id,

        p.job_title::text AS job_title,
        p.company_name::text AS company_name,
        p.location_text::text AS location_text,
        p.redirect_url::text AS redirect_url,

        p.source_created_at::timestamptz AS source_created_at,
        p.first_seen_at::timestamptz AS first_seen_at,
        p.last_seen_at::timestamptz AS last_seen_at,
        p.latest_collected_at::timestamptz AS latest_collected_at,

        p.observation_count::integer AS observation_count,

        p.salary_min::numeric AS salary_min,
        p.salary_max::numeric AS salary_max,
        p.salary_midpoint::numeric AS salary_midpoint,
        p.salary_currency::text AS salary_currency,
        p.salary_period::text AS salary_period,
        p.salary_parse_status::text AS salary_parse_status,
        p.salary_is_predicted::boolean AS salary_is_predicted,

        p.role_family::text AS role_family,
        p.seniority_level::text AS seniority_level,
        p.work_mode::text AS work_mode,
        p.classification_rule::text AS classification_rule,
        p.classification_confidence::text AS classification_confidence,

        p.country_code::text AS country_code,
        p.search_keyword::text AS search_keyword,
        p.search_location::text AS search_location,

        p.category_label::text AS category_label,
        p.category_tag::text AS category_tag,
        p.contract_time::text AS contract_time,
        p.contract_type::text AS contract_type,

        p.latitude::numeric AS latitude,
        p.longitude::numeric AS longitude,

        p.latest_record_hash::text AS latest_record_hash

    FROM prepared p

    LEFT JOIN {{ ref('dim_companies') }} c
        ON p.company_name_normalized = c.company_name_normalized

    LEFT JOIN {{ ref('dim_roles') }} d
        ON p.role_family = d.role_family
       AND p.seniority_level = d.seniority_level
       AND p.work_mode = d.work_mode

)

SELECT *
FROM with_dimension_keys