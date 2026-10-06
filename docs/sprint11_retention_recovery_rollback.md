# Sprint 11 — Retention, Recovery and Rollback

## Purpose

Sprint 11 defines how the project handles data retention, recovery, and rollback.

The goal is to make operational behavior explicit so that old data is cleaned safely, bad batches can be excluded logically, and the warehouse can be rebuilt from preserved raw data when needed.

---

# 1. Retention Policies

Retention policies are stored in the database table:

```text
raw.retention_policies
```

This table defines what data is retained, how long it is retained, and what cleanup action should be applied.

## Retention Policy Table

| Policy name | Target | Retention |
|---|---|---:|
| `raw_successful_observations` | `raw.source_adzuna_jobs` | 180 days |
| `raw_api_responses` | `raw.adzuna_api_responses` | 180 days |
| `quarantined_records` | `raw.quarantined_records` | 90 days |
| `ingestion_metadata` | `raw.ingestion_batches` | 365 days |
| `pipeline_metadata` | `ops.pipeline_runs` | 365 days |
| `snapshot_history` | `dev_snapshots.job_postings_snapshot` | 730 days |
| `local_dbt_logs` | `dbt_job_market/logs` | 90 days |

---

# 2. Retention Execution

Retention cleanup is handled by:

```text
scripts/apply_retention_policies.py
```

The script supports two modes:

```bash
make retention-dry-run
```

and:

```bash
make retention-apply
```

## Dry-run mode

Dry-run mode counts eligible records but does not delete anything.

This is the default safety mode.

## Execute mode

Execute mode deletes records that are eligible under the enabled retention policies.

Cleanup should only be applied after reviewing the dry-run output.

---

# 3. Snapshot Retention

dbt snapshots preserve historical versions of job postings.

The snapshot table contains two types of rows:

## Current rows

Current rows have:

```text
dbt_valid_to IS NULL
```

These rows represent the latest known version of each job posting.

Current rows must not be deleted by retention cleanup.

## Closed historical rows

Closed historical rows have:

```text
dbt_valid_to IS NOT NULL
```

These rows represent older versions of job postings that have already been replaced by newer versions.

Only closed historical rows are eligible for snapshot retention cleanup.

The cleanup condition is:

```sql
dbt_valid_to IS NOT NULL
AND dbt_valid_to < NOW() - INTERVAL '730 days'
```

---

# 4. Recovery Strategy

The warehouse is recoverable because raw data is preserved for a defined retention period.

## dbt transformation bug recovery

If a dbt model contains a bug, the recovery process is:

```text
bug in dbt model
        ↓
fix SQL logic
        ↓
run dbt build --full-refresh
        ↓
reconstruct warehouse from preserved raw data
```

Recommended command:

```bash
dbt build --full-refresh --project-dir dbt_job_market --profiles-dir dbt_job_market
```

This works because the raw layer preserves source observations separately from the transformed warehouse outputs.

---

# 5. Snapshot Recovery

Snapshots represent historical state and should be handled more carefully than normal marts.

If snapshot logic is wrong, the recommended process is:

1. Identify the incorrect snapshot logic.
2. Review the affected snapshot rows.
3. Decide whether historical correctness can be sacrificed.
4. Export or back up the existing snapshot if needed.
5. Rebuild the snapshot only if the historical loss is acceptable.

Snapshots should not be casually dropped or full-refreshed because they preserve historical versions.

---

# 6. Logical Rollback

The project uses logical rollback instead of immediately deleting raw data.

## Failed ingestion batch

A failed batch has:

```text
status = FAILED
```

The staging layer only reads successful batches.

Therefore failed batches remain in raw metadata but do not flow into the warehouse.

## Partial ingestion batch

A partial batch has:

```text
status = PARTIAL
```

In the current design, partial batches are also excluded from staging.

This is conservative and prevents incomplete data from reaching analytical marts.

## Bad successful batch

If a batch was marked as `SUCCESS` but later found to be bad, the rollback process is:

1. Investigate the batch.
2. Update the batch status to `FAILED` or `PARTIAL`.
3. Rerun dbt build.
4. The staging layer excludes that batch.
5. The warehouse and marts are reconstructed without that batch.

This preserves auditability because the raw data remains available until retention cleanup removes it.

---

# 7. Environment Promotion

The project uses a simple promotion model:

```text
dev → test → prod
```

## dev

Used for active development and local validation.

## test

Used for testing transformations before production use.

## prod

Used for stable dashboard and reporting outputs.

This is intentionally simpler than blue-green deployment.

Blue-green deployment can be added later if atomic production swaps or zero-downtime releases become necessary.

---

# 8. Disaster Recovery Assumptions

Recovery depends on:

- raw data being retained for the defined retention period
- dbt project code being committed to Git
- database backups existing for critical environments
- environment variables being stored securely
- deterministic surrogate keys being used
- dbt builds being reproducible

If marts are lost but raw data is still available, the warehouse can be rebuilt.

If raw data has already been deleted by retention cleanup, only retained snapshots, existing marts, and database backups can be used.

---

# 9. Key Rules

- Do not delete current snapshot rows.
- Do not manually edit marts.
- Use dry-run before applying retention cleanup.
- Prefer logical rollback over destructive raw edits.
- Keep retention policies visible and queryable.
- Preserve raw data long enough to support recovery.
- Use Git history to recover transformation logic.
- Use `dbt build --full-refresh` to recover from transformation bugs when raw data is still available.