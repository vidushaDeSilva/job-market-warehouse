"""
run_adzuna_ingestion.py

Command-line entry point for Sprint 2 Adzuna ingestion.

This script runs the minimal live ingestion flow:

    Adzuna API
        -> raw.adzuna_api_responses
        -> raw.source_adzuna_jobs
        -> raw.quarantined_records if needed

Before running this script, make sure:
1. Sprint 1 database setup has been applied with `make db-init`
2. ADZUNA_APP_ID and ADZUNA_APP_KEY are set in .env
"""

from job_market.ingestion.adzuna_loader import run_adzuna_ingestion

if __name__ == "__main__":
    run_adzuna_ingestion()
