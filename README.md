# Job Market Analytics Warehouse

This project is a data engineering portfolio project built around a live job-market data source.

The first production source will be the Adzuna Jobs API. The pipeline will collect job postings, store raw API data in PostgreSQL, transform it using dbt, and produce analytics marts for job-market insights such as skill demand, role trends, company hiring patterns, and data quality health.

## Project Goals

The project is designed to demonstrate practical data engineering skills:

- API-based batch ingestion
- raw data landing
- metadata and batch tracking
- dbt staging, intermediate, and mart models
- dimensional modeling
- incremental processing
- dbt tests and source freshness
- snapshots for historical changes
- data quality monitoring
- pipeline observability
- retry, rollback, idempotency, and retention design
- CI/CD and environment separation

