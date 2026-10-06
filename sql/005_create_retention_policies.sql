-- 005_create_retention_policies.sql
--
-- Sprint 11 retention policy metadata.
--
-- This table documents how long each class of data should be retained.
-- The cleanup script reads this table and applies only whitelisted policies.

CREATE TABLE IF NOT EXISTS raw.retention_policies (
    policy_name TEXT PRIMARY KEY,

    data_area TEXT NOT NULL,
    target_type TEXT NOT NULL,
    target_identifier TEXT NOT NULL,

    retention_days INTEGER NOT NULL,
    retention_action TEXT NOT NULL DEFAULT 'delete',

    is_enabled BOOLEAN NOT NULL DEFAULT TRUE,
    protect_current_records BOOLEAN NOT NULL DEFAULT TRUE,

    notes TEXT,

    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT chk_retention_days_positive
        CHECK (retention_days > 0),

    CONSTRAINT chk_retention_action
        CHECK (retention_action IN ('delete', 'archive_then_delete')),

    CONSTRAINT chk_retention_target_type
        CHECK (target_type IN ('database_table', 'local_directory'))
);

INSERT INTO raw.retention_policies (
    policy_name,
    data_area,
    target_type,
    target_identifier,
    retention_days,
    retention_action,
    is_enabled,
    protect_current_records,
    notes
)
VALUES
    (
        'raw_successful_observations',
        'raw',
        'database_table',
        'raw.source_adzuna_jobs',
        180,
        'delete',
        TRUE,
        TRUE,
        'Deletes old successful raw job observations. Failed and quarantined records are handled separately.'
    ),
    (
        'raw_api_responses',
        'raw',
        'database_table',
        'raw.adzuna_api_responses',
        180,
        'delete',
        TRUE,
        TRUE,
        'Deletes old stored API response payloads after the raw observation retention window.'
    ),
    (
        'quarantined_records',
        'raw',
        'database_table',
        'raw.quarantined_records',
        90,
        'delete',
        TRUE,
        TRUE,
        'Deletes old quarantined records after review window.'
    ),
    (
        'ingestion_metadata',
        'raw',
        'database_table',
        'raw.ingestion_batches',
        365,
        'delete',
        TRUE,
        TRUE,
        'Deletes old ingestion batch metadata. Cascades to remaining raw children if any exist.'
    ),
    (
        'pipeline_metadata',
        'ops',
        'database_table',
        'ops.pipeline_runs',
        365,
        'delete',
        TRUE,
        TRUE,
        'Deletes old observed pipeline run metadata.'
    ),
    (
        'snapshot_history',
        'snapshots',
        'database_table',
        'target_schema_snapshots.job_postings_snapshot',
        730,
        'delete',
        TRUE,
        TRUE,
        'Deletes only closed historical snapshot rows. Current dbt snapshot rows are never deleted.'
    ),
    (
        'local_dbt_logs',
        'logs',
        'local_directory',
        'dbt_job_market/logs',
        90,
        'delete',
        TRUE,
        TRUE,
        'Deletes local dbt log files older than the retention window.'
    )
ON CONFLICT (policy_name) DO UPDATE
SET
    data_area = EXCLUDED.data_area,
    target_type = EXCLUDED.target_type,
    target_identifier = EXCLUDED.target_identifier,
    retention_days = EXCLUDED.retention_days,
    retention_action = EXCLUDED.retention_action,
    is_enabled = EXCLUDED.is_enabled,
    protect_current_records = EXCLUDED.protect_current_records,
    notes = EXCLUDED.notes,
    updated_at = NOW();