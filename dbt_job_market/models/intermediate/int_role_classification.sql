-- int_role_classification.sql
--
-- Role classification model.
--
-- Grain:
--   One row per canonical job.
--
-- Purpose:
--   Convert messy job titles into standardized analytical role families.
--
-- Design principle:
--   If classification is not clear, return "unknown" instead of forcing a
--   misleading category.

WITH jobs AS (

    SELECT *
    FROM {{ ref('int_job_posting_deduped') }}

),

prepared AS (

    SELECT
        job_id,
        job_title,
        description_text_clean,
        category_label,

        LOWER(
            CONCAT_WS(
                ' ',
                COALESCE(job_title, ''),
                COALESCE(category_label, ''),
                COALESCE(description_text_clean, '')
            )
        ) AS classification_text

    FROM jobs

),

classified AS (

    SELECT
        job_id,
        job_title,

        CASE
            WHEN classification_text ~* 'analytics engineer|dbt developer|dbt engineer|bi engineer'
                THEN 'analytics_engineering'

            WHEN classification_text ~* 'data engineer|etl engineer|data platform engineer|data warehouse engineer|big data engineer|pipeline engineer'
                THEN 'data_engineering'

            WHEN classification_text ~* 'data analyst|business intelligence analyst|bi analyst|reporting analyst|insight analyst|analytics analyst'
                THEN 'data_analytics'

            WHEN classification_text ~* 'data scientist|machine learning engineer|ml engineer|ai engineer|applied scientist'
                THEN 'data_science'

            WHEN classification_text ~* 'software engineer|backend engineer|front end engineer|frontend engineer|full stack engineer|developer|devops engineer|cloud engineer'
                THEN 'software_engineering'

            WHEN classification_text ~* 'sales|account executive|recruiter|talent acquisition|product manager|marketing|finance manager'
                THEN 'other'

            ELSE 'unknown'
        END AS role_family,

        CASE
            WHEN classification_text ~* 'intern|internship|placement'
                THEN 'internship'

            WHEN classification_text ~* 'junior|jr\.|graduate|entry level|entry-level|associate'
                THEN 'entry'

            WHEN classification_text ~* 'lead|principal|staff|head of|manager|director'
                THEN 'lead'

            WHEN classification_text ~* 'senior|sr\.'
                THEN 'senior'

            WHEN classification_text ~* 'data engineer|analytics engineer|data analyst|data scientist|software engineer|developer|etl engineer'
                THEN 'mid'

            ELSE 'unknown'
        END AS seniority_level,

        CASE
            WHEN classification_text ~* 'remote|work from home|wfh'
                THEN 'remote'

            WHEN classification_text ~* 'hybrid'
                THEN 'hybrid'

            WHEN classification_text ~* 'on-site|onsite|office based|office-based'
                THEN 'onsite'

            ELSE 'unknown'
        END AS work_mode,

        CASE
            WHEN classification_text ~* 'analytics engineer|dbt developer|dbt engineer|bi engineer'
                THEN 'role_keyword_analytics_engineering'

            WHEN classification_text ~* 'data engineer|etl engineer|data platform engineer|data warehouse engineer|big data engineer|pipeline engineer'
                THEN 'role_keyword_data_engineering'

            WHEN classification_text ~* 'data analyst|business intelligence analyst|bi analyst|reporting analyst|insight analyst|analytics analyst'
                THEN 'role_keyword_data_analytics'

            WHEN classification_text ~* 'data scientist|machine learning engineer|ml engineer|ai engineer|applied scientist'
                THEN 'role_keyword_data_science'

            WHEN classification_text ~* 'software engineer|backend engineer|front end engineer|frontend engineer|full stack engineer|developer|devops engineer|cloud engineer'
                THEN 'role_keyword_software_engineering'

            WHEN classification_text ~* 'sales|account executive|recruiter|talent acquisition|product manager|marketing|finance manager'
                THEN 'role_keyword_other'

            ELSE 'no_confident_rule'
        END AS classification_rule,

        CASE
            WHEN classification_text ~* 'analytics engineer|data engineer|etl engineer|data analyst|data scientist|machine learning engineer|software engineer'
                THEN 'high'

            WHEN classification_text ~* 'developer|analyst|engineer'
                THEN 'medium'

            ELSE 'low'
        END AS classification_confidence

    FROM prepared

)

SELECT *
FROM classified