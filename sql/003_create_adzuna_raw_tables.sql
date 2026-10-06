/*
003_create_adzuna_raw_tables.sql

Creates the raw landing tables for Adzuna API ingestion.


1. raw.adzuna_api_responses
   - one row per Adzuna API request/page
   - stores request metadata and the full JSON response

2. raw.source_adzuna_jobs
   - one row per job observation returned by Adzuna
   - stores parsed fields plus the original job payload

3. raw.quarantined_records
   - stores records that failed validation or parsing
   - prevents one bad job record from breaking the whole batch

These tables preserve raw source evidence. dbt will later build clean,
deduplicated, analytics-ready models from these raw tables.
*/


-- ============================================================
-- 1. raw.adzuna_api_responses
-- ============================================================
--
-- Grain:
-- One row per Adzuna API request/page.
--
-- Example:
-- Query: data engineer, London, GB
-- Page: 1
-- Response: 50 jobs
--
-- We intentionally store the full raw_response_json so that we can
-- re-parse or debug API responses later if the transformation logic changes.
-- ============================================================

CREATE TABLE IF NOT EXISTS raw.adzuna_api_responses (
    api_response_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    batch_id UUID NOT NULL,
    query_config_id BIGINT NOT NULL,

    source_name TEXT NOT NULL DEFAULT 'adzuna',

    country_code VARCHAR(2) NOT NULL,
    keyword TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',

    page_number INTEGER NOT NULL,
    results_per_page INTEGER NOT NULL,

    -- We do not store the full request URL because API credentials can appear
    -- in query parameters. Instead, we store safe request parameters and a hash.
    request_url_hash TEXT NOT NULL,
    request_params_json JSONB NOT NULL,

    response_status_code INTEGER NOT NULL,
    response_received_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    records_returned INTEGER NOT NULL DEFAULT 0,
    total_count INTEGER,

    raw_response_json JSONB NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_adzuna_response_batch
        FOREIGN KEY (batch_id)
        REFERENCES raw.ingestion_batches(batch_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_adzuna_response_query
        FOREIGN KEY (query_config_id)
        REFERENCES raw.adzuna_query_config(query_config_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_adzuna_response_page
        CHECK (page_number > 0),

    CONSTRAINT chk_adzuna_response_results_per_page
        CHECK (results_per_page > 0),

    CONSTRAINT chk_adzuna_response_status
        CHECK (response_status_code >= 100 AND response_status_code <= 599),

    CONSTRAINT chk_adzuna_response_counts
        CHECK (
            records_returned >= 0
            AND (total_count IS NULL OR total_count >= 0)
        )
);


CREATE INDEX IF NOT EXISTS idx_adzuna_api_responses_batch
    ON raw.adzuna_api_responses (batch_id);


CREATE INDEX IF NOT EXISTS idx_adzuna_api_responses_query_page
    ON raw.adzuna_api_responses (query_config_id, page_number);


CREATE INDEX IF NOT EXISTS idx_adzuna_api_responses_received_at
    ON raw.adzuna_api_responses (response_received_at DESC);


-- ============================================================
-- 2. raw.source_adzuna_jobs
-- ============================================================
--
-- Grain:
-- One row per Adzuna job observation.
--
-- If the same Adzuna job appears on Monday and Tuesday, raw should keep
-- both observations. dbt will later create canonical deduplicated jobs.
-- ============================================================

CREATE TABLE IF NOT EXISTS raw.source_adzuna_jobs (
    raw_adzuna_job_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    api_response_id UUID NOT NULL,
    batch_id UUID NOT NULL,
    query_config_id BIGINT NOT NULL,

    source_name TEXT NOT NULL DEFAULT 'adzuna',

    adzuna_job_id TEXT,

    title TEXT NOT NULL,
    company_name TEXT NOT NULL,
    location_text TEXT,
    description_text TEXT NOT NULL,

    redirect_url TEXT,

    source_created_at TIMESTAMPTZ,

    salary_min NUMERIC,
    salary_max NUMERIC,
    salary_is_predicted TEXT,

    category_label TEXT,
    category_tag TEXT,

    contract_time TEXT,
    contract_type TEXT,

    latitude NUMERIC,
    longitude NUMERIC,

    country_code VARCHAR(2) NOT NULL,
    search_keyword TEXT NOT NULL,
    search_location TEXT NOT NULL DEFAULT '',

    collected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- Hash of selected source fields. This helps later with deduplication,
    -- change detection, and idempotency checks.
    record_hash TEXT NOT NULL,

    raw_payload JSONB NOT NULL,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_source_adzuna_jobs_response
        FOREIGN KEY (api_response_id)
        REFERENCES raw.adzuna_api_responses(api_response_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_source_adzuna_jobs_batch
        FOREIGN KEY (batch_id)
        REFERENCES raw.ingestion_batches(batch_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_source_adzuna_jobs_query
        FOREIGN KEY (query_config_id)
        REFERENCES raw.adzuna_query_config(query_config_id)
        ON DELETE CASCADE,

    CONSTRAINT chk_source_adzuna_salary
        CHECK (
            salary_min IS NULL
            OR salary_max IS NULL
            OR salary_min <= salary_max
        )
);


CREATE INDEX IF NOT EXISTS idx_source_adzuna_jobs_batch
    ON raw.source_adzuna_jobs (batch_id);


CREATE INDEX IF NOT EXISTS idx_source_adzuna_jobs_response
    ON raw.source_adzuna_jobs (api_response_id);


CREATE INDEX IF NOT EXISTS idx_source_adzuna_jobs_adzuna_id
    ON raw.source_adzuna_jobs (adzuna_job_id);


CREATE INDEX IF NOT EXISTS idx_source_adzuna_jobs_record_hash
    ON raw.source_adzuna_jobs (record_hash);


CREATE INDEX IF NOT EXISTS idx_source_adzuna_jobs_collected_at
    ON raw.source_adzuna_jobs (collected_at DESC);


CREATE INDEX IF NOT EXISTS idx_source_adzuna_jobs_source_created_at
    ON raw.source_adzuna_jobs (source_created_at DESC);


-- ============================================================
-- 3. raw.quarantined_records
-- ============================================================
--
-- Grain:
-- One row per rejected or failed record.
--
-- We do not silently drop bad records. If a job payload is malformed or
-- missing required fields, it goes here for later review.
-- ============================================================

CREATE TABLE IF NOT EXISTS raw.quarantined_records (
    quarantine_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    batch_id UUID NOT NULL,
    api_response_id UUID,
    query_config_id BIGINT,

    source_name TEXT NOT NULL DEFAULT 'adzuna',

    failure_stage TEXT NOT NULL,
    failure_reason TEXT NOT NULL,

    raw_payload JSONB NOT NULL,

    is_resolved BOOLEAN NOT NULL DEFAULT FALSE,
    resolved_at TIMESTAMPTZ,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_quarantined_batch
        FOREIGN KEY (batch_id)
        REFERENCES raw.ingestion_batches(batch_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_quarantined_response
        FOREIGN KEY (api_response_id)
        REFERENCES raw.adzuna_api_responses(api_response_id)
        ON DELETE SET NULL,

    CONSTRAINT fk_quarantined_query
        FOREIGN KEY (query_config_id)
        REFERENCES raw.adzuna_query_config(query_config_id)
        ON DELETE SET NULL,

    CONSTRAINT chk_quarantined_resolution_time
        CHECK (
            resolved_at IS NULL
            OR is_resolved = TRUE
        )
);


CREATE INDEX IF NOT EXISTS idx_quarantined_batch
    ON raw.quarantined_records (batch_id);


CREATE INDEX IF NOT EXISTS idx_quarantined_created_at
    ON raw.quarantined_records (created_at DESC);


CREATE INDEX IF NOT EXISTS idx_quarantined_is_resolved
    ON raw.quarantined_records (is_resolved);