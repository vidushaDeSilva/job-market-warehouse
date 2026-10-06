-- 004_observability_indexes.sql
--
-- Sprint 10 observability support.
--
-- The main ops.pipeline_runs table already exists from Sprint 1.
-- This migration only adds safety columns if missing and adds helpful indexes.

ALTER TABLE ops.pipeline_runs
ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE ops.pipeline_runs
ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT NOW();

ALTER TABLE ops.pipeline_runs
ADD COLUMN IF NOT EXISTS dbt_invocation_id TEXT;

ALTER TABLE ops.pipeline_runs
ADD COLUMN IF NOT EXISTS dbt_status TEXT;

ALTER TABLE ops.pipeline_runs
ADD COLUMN IF NOT EXISTS tests_passed INTEGER DEFAULT 0;

ALTER TABLE ops.pipeline_runs
ADD COLUMN IF NOT EXISTS tests_failed INTEGER DEFAULT 0;

ALTER TABLE ops.pipeline_runs
ADD COLUMN IF NOT EXISTS git_sha TEXT;

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_started_at
ON ops.pipeline_runs(started_at DESC);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_status
ON ops.pipeline_runs(status);

CREATE INDEX IF NOT EXISTS idx_pipeline_runs_ingestion_batch
ON ops.pipeline_runs(ingestion_batch_id);

CREATE INDEX IF NOT EXISTS idx_ingestion_batches_source_started_at
ON raw.ingestion_batches(source_name, started_at DESC);

CREATE INDEX IF NOT EXISTS idx_api_responses_batch_status
ON raw.adzuna_api_responses(batch_id, response_status_code);