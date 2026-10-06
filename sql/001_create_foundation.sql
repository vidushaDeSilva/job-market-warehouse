/*
001_create_foundation.sql

Creates the database foundation for the Job Market Analytics Warehouse.

Schema ownership:
    raw -> source ingestion data and ingestion metadata
    ops -> operational pipeline state and monitoring metadata

dbt-generated schemas such as dev_staging and dev_marts are intentionally
not created here because dbt will own them later.
*/


-- ============================================================
-- 1. Schemas
-- ============================================================

CREATE SCHEMA IF NOT EXISTS raw;
CREATE SCHEMA IF NOT EXISTS ops;


-- ============================================================
-- 2. raw.ingestion_batches
-- ============================================================
--
-- Grain:
-- One row represents one Adzuna ingestion attempt.
--
-- A batch may contain results from several configured Adzuna queries.
--
-- Keeping batch metadata allows us to:
--   - identify successful and failed loads
--   - retry failed ingestion safely
--   - prevent dbt from consuming failed batches
--   - audit how many records were received and loaded
-- ============================================================

CREATE TABLE IF NOT EXISTS raw.ingestion_batches (
    batch_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    pipeline_name TEXT NOT NULL DEFAULT 'adzuna_job_ingestion',
    source_name TEXT NOT NULL DEFAULT 'adzuna',

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,

    status TEXT NOT NULL DEFAULT 'STARTED',

    records_expected INTEGER,
    records_received INTEGER NOT NULL DEFAULT 0,
    records_loaded INTEGER NOT NULL DEFAULT 0,
    records_quarantined INTEGER NOT NULL DEFAULT 0,

    api_requests_made INTEGER NOT NULL DEFAULT 0,
    api_success_count INTEGER NOT NULL DEFAULT 0,
    api_failure_count INTEGER NOT NULL DEFAULT 0,
    api_rate_limit_hit BOOLEAN NOT NULL DEFAULT FALSE,

    retry_count INTEGER NOT NULL DEFAULT 0,
    max_retries INTEGER NOT NULL DEFAULT 3,

    last_retry_at TIMESTAMPTZ,
    next_retry_at TIMESTAMPTZ,

    failure_type TEXT,
    is_retryable BOOLEAN,
    error_message TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_ingestion_batch_status
        CHECK (
            status IN (
                'STARTED',
                'SUCCESS',
                'FAILED',
                'PARTIAL'
            )
        ),

    CONSTRAINT chk_ingestion_batch_times
        CHECK (
            finished_at IS NULL
            OR finished_at >= started_at
        ),

    CONSTRAINT chk_ingestion_batch_counts
        CHECK (
            records_received >= 0
            AND records_loaded >= 0
            AND records_quarantined >= 0
            AND api_requests_made >= 0
            AND api_success_count >= 0
            AND api_failure_count >= 0
            AND retry_count >= 0
            AND max_retries >= 0
        )
);


-- Useful for finding the most recent ingestion batches.
CREATE INDEX IF NOT EXISTS idx_ingestion_batches_started_at
    ON raw.ingestion_batches (started_at DESC);


-- Useful for operational queries such as:
-- "show me all failed batches".
CREATE INDEX IF NOT EXISTS idx_ingestion_batches_status
    ON raw.ingestion_batches (status);


-- ============================================================
-- 3. raw.adzuna_query_config
-- ============================================================
--
-- Grain:
-- One row represents one Adzuna search configuration.
--
-- Instead of hardcoding searches such as:
--
--     "data engineer in London"
--
-- inside Python, they are stored as data.
--
-- The ingestion pipeline will later read all rows where
-- is_active = TRUE and execute those searches.
-- ============================================================

CREATE TABLE IF NOT EXISTS raw.adzuna_query_config (
    query_config_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,

    country_code VARCHAR(2) NOT NULL,
    keyword TEXT NOT NULL,
    location TEXT NOT NULL DEFAULT '',

    results_per_page INTEGER NOT NULL DEFAULT 50,
    max_pages INTEGER NOT NULL DEFAULT 2,

    is_active BOOLEAN NOT NULL DEFAULT TRUE,

    description TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_adzuna_query
        UNIQUE (country_code, keyword, location),

    CONSTRAINT chk_adzuna_country_code
        CHECK (country_code = LOWER(country_code)),

    CONSTRAINT chk_adzuna_results_per_page
        CHECK (
            results_per_page > 0
            AND results_per_page <= 50
        ),

    CONSTRAINT chk_adzuna_max_pages
        CHECK (max_pages > 0)
);


-- The ingestion process will mostly request active configurations.
CREATE INDEX IF NOT EXISTS idx_adzuna_query_config_active
    ON raw.adzuna_query_config (is_active);


-- ============================================================
-- 4. ops.pipeline_runs
-- ============================================================
--
-- Grain:
-- One row represents one complete execution of the data pipeline.
--
-- This differs from ingestion_batches.
--
-- ingestion_batches:
--     Tracks Adzuna collection.
--
-- pipeline_runs:
--     Tracks the full process:
--
--     ingestion -> dbt -> tests -> publication
--
-- dbt-related fields are included now even though dbt execution will
-- be connected in a later sprint.
-- ============================================================

CREATE TABLE IF NOT EXISTS ops.pipeline_runs (
    pipeline_run_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),

    pipeline_name TEXT NOT NULL DEFAULT 'job_market_pipeline',

    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,

    status TEXT NOT NULL DEFAULT 'STARTED',

    trigger_type TEXT NOT NULL DEFAULT 'MANUAL',

    ingestion_batch_id UUID,

    dbt_invocation_id TEXT,
    dbt_status TEXT NOT NULL DEFAULT 'NOT_STARTED',

    tests_passed INTEGER NOT NULL DEFAULT 0,
    tests_failed INTEGER NOT NULL DEFAULT 0,

    git_commit_sha VARCHAR(40),

    error_message TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_pipeline_ingestion_batch
        FOREIGN KEY (ingestion_batch_id)
        REFERENCES raw.ingestion_batches(batch_id)
        ON DELETE SET NULL,

    CONSTRAINT chk_pipeline_status
        CHECK (
            status IN (
                'STARTED',
                'SUCCESS',
                'FAILED',
                'PARTIAL'
            )
        ),

    CONSTRAINT chk_pipeline_trigger_type
        CHECK (
            trigger_type IN (
                'MANUAL',
                'SCHEDULED',
                'CI'
            )
        ),

    CONSTRAINT chk_pipeline_dbt_status
        CHECK (
            dbt_status IN (
                'NOT_STARTED',
                'RUNNING',
                'SUCCESS',
                'FAILED',
                'SKIPPED'
            )
        ),

    CONSTRAINT chk_pipeline_times
        CHECK (
            finished_at IS NULL
            OR finished_at >= started_at
        ),

    CONSTRAINT chk_pipeline_test_counts
        CHECK (
            tests_passed >= 0
            AND tests_failed >= 0
        )
);


CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at
    ON ops.pipeline_runs (started_at DESC);


CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status
    ON ops.pipeline_runs (status);


-- ============================================================
-- 5. ops.source_collection_state
-- ============================================================
--
-- Grain:
-- One row per Adzuna query configuration.
--
-- This table records where ingestion last succeeded.
--
-- It becomes useful later for:
--   - incremental collection
--   - restarting after failures
--   - freshness monitoring
--   - understanding when each query was last successfully collected
-- ============================================================

CREATE TABLE IF NOT EXISTS ops.source_collection_state (
    source_name TEXT NOT NULL DEFAULT 'adzuna',

    query_config_id BIGINT NOT NULL,

    last_successful_run_at TIMESTAMPTZ,
    last_successful_page INTEGER,

    -- Timestamp of the newest source-side job observed during
    -- the latest successful ingestion.
    last_record_created_at TIMESTAMPTZ,

    last_batch_id UUID,

    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    PRIMARY KEY (source_name, query_config_id),

    CONSTRAINT fk_collection_state_query
        FOREIGN KEY (query_config_id)
        REFERENCES raw.adzuna_query_config(query_config_id)
        ON DELETE CASCADE,

    CONSTRAINT fk_collection_state_batch
        FOREIGN KEY (last_batch_id)
        REFERENCES raw.ingestion_batches(batch_id)
        ON DELETE SET NULL,

    CONSTRAINT chk_collection_state_page
        CHECK (
            last_successful_page IS NULL
            OR last_successful_page > 0
        )
);


CREATE INDEX IF NOT EXISTS idx_collection_state_batch
    ON ops.source_collection_state (last_batch_id);