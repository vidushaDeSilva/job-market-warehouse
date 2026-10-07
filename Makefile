# ------------------------------------------------------------------
# Makefile
#
# Common development commands for the Job Market Analytics Warehouse.
#
# Run these commands inside an activated Python virtual environment.
# ------------------------------------------------------------------

PYTHON := python
PIP := pip
DBT := dbt

.PHONY: \
	install \
	check-db \
	db-init \
	ingest-adzuna \
	observed-pipeline \
	dbt-debug \
	dbt-parse \
	dbt-seed \
	dbt-build \
	dbt-test \
	dbt-freshness \
	dbt-snapshot \
	sprint0-check \
	sprint1-check \
	sprint2-check \
	sprint3-check \
	sprint4-check \
	sprint5-check \
	sprint6-check \
	sprint7-check \
	sprint8-check \
	sprint9-check \
	sprint10-check \
	retention-dry-run \
	retention-apply \
	dbt-build-full-refresh \
	dbt-build-test \
	sprint11-check \
	orchestrated-pipeline \
	sprint13-check \
	lint \
	test \
	dbt-deps \
	dbt-compile \
	dbt-build-ci \
	ci-check \
	drop-ci-schemas \
	dashboard \
	sprint15-check \
	clean


install:
	$(PIP) install -e .


check-db:
	$(PYTHON) scripts/check_db_connection.py


db-init:
	$(PYTHON) scripts/init_database.py


ingest-adzuna:
	$(PYTHON) scripts/run_adzuna_ingestion.py


observed-pipeline:
	$(PYTHON) scripts/orchestrate_pipeline.py


dbt-debug:
	set -a; [ -f .env ] && . ./.env; set +a; \
	$(DBT) debug --project-dir dbt_job_market --profiles-dir dbt_job_market


dbt-parse:
	set -a; [ -f .env ] && . ./.env; set +a; \
	$(DBT) parse --project-dir dbt_job_market --profiles-dir dbt_job_market


dbt-seed:
	set -a; [ -f .env ] && . ./.env; set +a; \
	$(DBT) seed --project-dir dbt_job_market --profiles-dir dbt_job_market


dbt-build:
	set -a; [ -f .env ] && . ./.env; set +a; \
	$(DBT) build --project-dir dbt_job_market --profiles-dir dbt_job_market


dbt-test:
	set -a; [ -f .env ] && . ./.env; set +a; \
	$(DBT) test --project-dir dbt_job_market --profiles-dir dbt_job_market


dbt-freshness:
	set -a; [ -f .env ] && . ./.env; set +a; \
	$(DBT) source freshness --project-dir dbt_job_market --profiles-dir dbt_job_market


dbt-snapshot:
	set -a; [ -f .env ] && . ./.env; set +a; \
	$(DBT) snapshot --project-dir dbt_job_market --profiles-dir dbt_job_market


sprint0-check: check-db dbt-debug dbt-parse


sprint1-check:
	$(PYTHON) scripts/check_sprint1.py


sprint2-check:
	$(PYTHON) scripts/check_sprint2.py


sprint3-check:
	$(PYTHON) scripts/check_sprint3.py


sprint4-check: dbt-build dbt-freshness


sprint5-check: dbt-build
	$(PYTHON) scripts/check_sprint5.py


sprint6-check: dbt-build
	$(PYTHON) scripts/check_sprint6.py


sprint7-check: dbt-build
	$(PYTHON) scripts/check_sprint7.py


sprint8-check: dbt-build
	$(PYTHON) scripts/check_sprint8.py


sprint9-check: dbt-build dbt-snapshot
	$(PYTHON) scripts/check_sprint9.py


sprint10-check:
	$(PYTHON) scripts/check_sprint10.py


clean:
	rm -rf dbt_job_market/target
	rm -rf dbt_job_market/logs
	rm -rf dbt_job_market/dbt_packages
	rm -rf *.egg-info
	rm -rf ingestion/src/*.egg-info


retention-dry-run:
	$(PYTHON) scripts/apply_retention_policies.py


retention-apply:
	$(PYTHON) scripts/apply_retention_policies.py --execute


dbt-build-full-refresh:
	set -a; [ -f .env ] && . ./.env; set +a; \
	$(DBT) build --full-refresh --project-dir dbt_job_market --profiles-dir dbt_job_market


dbt-build-test:
	set -a; [ -f .env ] && . ./.env; set +a; \
	$(DBT) build --target test --project-dir dbt_job_market --profiles-dir dbt_job_market


sprint11-check: db-init
	$(PYTHON) scripts/check_sprint11.py
	$(PYTHON) scripts/apply_retention_policies.py


orchestrated-pipeline:
	$(PYTHON) scripts/orchestrate_pipeline.py


sprint13-check:
	$(PYTHON) scripts/check_sprint13.py


lint:
	ruff check .


test:
	pytest


dbt-deps:
	set -a; [ -f .env ] && . ./.env; set +a; \
	$(DBT) deps --project-dir dbt_job_market --profiles-dir dbt_job_market


dbt-compile:
	set -a; [ -f .env ] && . ./.env; set +a; \
	$(DBT) compile --project-dir dbt_job_market --profiles-dir dbt_job_market


dbt-build-ci:
	set -a; [ -f .env ] && . ./.env; set +a; \
	DBT_SCHEMA=ci_local $(DBT) build --project-dir dbt_job_market --profiles-dir dbt_job_market --target ci


drop-ci-schemas:
	$(PYTHON) scripts/drop_dbt_ci_schemas.py


ci-check: lint test dbt-deps dbt-parse dbt-compile


dashboard:
	$(PYTHON) -m streamlit run dashboard/Home.py


sprint15-check: dbt-build
	$(PYTHON) scripts/check_sprint15.py