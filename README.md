# Job Market Analytics Warehouse

A production-style data engineering project that collects job market data from the Adzuna API, stores raw observations in PostgreSQL, transforms them with dbt, tracks data quality and pipeline health, and serves analytics through a lightweight Streamlit dashboard.

---

## 1. Architecture

Adzuna API
    ↓
Python ingestion
    ↓
PostgreSQL raw layer
    ↓
dbt staging
    ↓
dbt intermediate models
    ↓
dbt marts
    ↓
Streamlit dashboard

The project separates ingestion, transformation, orchestration, monitoring, and serving.

---

## 2. Data Source

The project uses the Adzuna API for job vacancy and salary-related data.

The dashboard acknowledges Adzuna as the source of the vacancy and salary data. Job-level records are shown with Adzuna attribution and links through the stored Adzuna redirect URL.

---

## 3. Data Model

### Raw layer

Raw data is stored in:

raw.ingestion_batches
raw.adzuna_api_responses
raw.source_adzuna_jobs
raw.quarantined_records
raw.adzuna_query_config

The raw layer preserves source observations for recovery and auditability.

### Staging layer

Staging models clean and standardize raw data:

stg_adzuna_jobs
stg_adzuna_api_responses
stg_ingestion_batches
stg_pipeline_runs

Staging keeps one clear grain per source table.

### Intermediate layer

Intermediate models apply business logic:

int_job_posting_deduped
int_salary_normalized
int_role_classification
int_job_skill_matches

This layer handles canonical job identity, salary normalization, role classification, and skill extraction.

### Mart layer

Marts are dashboard-ready serving tables:

fact_job_postings
fact_job_skill_mentions
dim_companies
dim_skills
dim_roles
mart_skill_demand_weekly
mart_company_hiring_summary
mart_role_market_summary
mart_job_market_overview
mart_salary_distribution
mart_pipeline_health
mart_api_request_summary
mart_ingestion_batch_summary
mart_data_quality_summary

Marts are materialized as tables for faster dashboard queries.

---

## 4. Pipeline

The complete pipeline is orchestrated by:

scripts/orchestrate_pipeline.py

Pipeline flow:

create pipeline_run
    ↓
run Adzuna ingestion
    ↓
validate ingestion batch
    ↓
dbt source freshness
    ↓
dbt build
    ↓
dbt snapshot
    ↓
update pipeline_run
    ↓
rebuild observability marts

Each run is tracked in:

ops.pipeline_runs

---

## 5. dbt Lineage

The dbt project follows a layered structure:

sources
  ↓
staging
  ↓
intermediate
  ↓
dimensions / facts
  ↓
analytical marts
  ↓
dashboard

dbt tests validate uniqueness, not-null constraints, accepted values, relationships, and custom business rules.

---

## 6. Failure Handling

Pipeline failures are explicitly recorded.

If ingestion fails, the pipeline stops before dbt builds downstream models.

If dbt tests fail, the pipeline records the failure and does not mark the run as successful.

Operational failures are visible in:

mart_pipeline_health
mart_ingestion_batch_summary
mart_api_request_summary
mart_data_quality_summary

---

## 7. Idempotency

The ingestion process appends source observations and records each ingestion batch.

dbt models use deterministic keys such as:

job_id
company_id
skill_id
role_id

Incremental models use stable unique keys and merge strategies to avoid unnecessary full rebuilds.

---

## 8. Retry

The Adzuna client handles retryable failures such as timeouts, network errors, rate limits, and server-side API errors.

Retry metadata is stored in:

raw.ingestion_batches

Tracked fields include retry count, max retries, rate-limit flags, failure type, and error message.

---

## 9. Rollback

The project uses logical rollback.

Failed batches remain in raw metadata but are excluded from staging and marts.

If a successful batch is later found to be bad, it can be marked as failed or partial and dbt can rebuild the warehouse without that batch.

---

## 10. Retention

Retention policies are stored in:

raw.retention_policies

Cleanup is handled by:

scripts/apply_retention_policies.py

Dry run:

make retention-dry-run

Apply cleanup:

make retention-apply

Current snapshot rows are protected. Only closed historical snapshot rows are eligible for snapshot retention cleanup.

---

## 11. Testing

Python tests are stored in:

ingestion/tests

Run:

pytest

dbt tests run with:

make dbt-test

Full dbt build:

make dbt-build

---

## 12. Observability

The project tracks:

last successful run
last successful ingestion
API requests
API failures
records received
records quarantined
dbt test status
data freshness
duplicate percentage
salary coverage
skill extraction coverage

Main observability marts:

mart_pipeline_health
mart_api_request_summary
mart_ingestion_batch_summary
mart_data_quality_summary

---

## 13. CI/CD

Pull requests run GitHub Actions CI:

Python lint
Python tests
dbt deps
dbt parse
dbt compile
dbt build in isolated CI schema
cleanup CI schema

CI uses temporary schemas such as:

ci_<run_id>_<attempt>_marts

Production deployment uses a separate protected workflow and the `prod` dbt target.

No credentials are committed to Git.

---

## 14. Dashboard

The Streamlit dashboard is in:

dashboard/

Run locally:

make dashboard

Pages:

Job Market Overview
Data Health
Job Explorer

The dashboard queries only prepared marts and caches query results for 900 seconds.

If job-level records are displayed, Adzuna attribution is shown.

---

## 15. How to Run Locally

Install dependencies:

python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

Initialize database:

make db-init

Run ingestion:

make ingest-adzuna

Build dbt models:

make dbt-build

Run snapshots:

make dbt-snapshot

Run full orchestrated pipeline:

make orchestrated-pipeline

Launch dashboard:

make dashboard

---

## 16. Example Analytics

The dashboard supports:

total unique jobs
jobs collected this week
remote share
salary coverage
top skills
skill demand over time
top hiring companies
role distribution
salary distribution
pipeline health
source freshness
API failures
quarantined records
dbt test status
data quality score

---

## 17. Environment Variables

Required local variables are stored in `.env`.

Never commit `.env`.

Use `.env.example` as the template.

Important variables:

DATABASE_URL
POSTGRES_HOST
POSTGRES_PORT
POSTGRES_USER
POSTGRES_PASSWORD
POSTGRES_DB
ADZUNA_APP_ID
ADZUNA_APP_KEY
DBT_SCHEMA
DASHBOARD_DATABASE_URL
DASHBOARD_SCHEMA

For production dashboard usage, `DASHBOARD_DATABASE_URL` should point to a read-only analytics database user.