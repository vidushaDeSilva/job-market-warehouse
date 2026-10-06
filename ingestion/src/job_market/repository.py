"""
repository.py

Database repository functions for ingestion workflows.

This module contains SQL operations used by the Adzuna ingestion pipeline:
creating batches, reading query configuration, inserting raw API responses,
inserting job observations, writing quarantined records, and updating
collection state.

"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from job_market.db import get_connection


@dataclass(frozen=True)
class AdzunaQueryConfig:
    """
    Active Adzuna query configuration read from raw.adzuna_query_config.
    """

    query_config_id: int
    country_code: str
    keyword: str
    location: str
    results_per_page: int
    max_pages: int


def create_ingestion_batch() -> UUID:
    """
    Create a new ingestion batch with status STARTED.

    Returns:
        UUID: New batch ID.
    """

    query = """
        INSERT INTO raw.ingestion_batches (
            pipeline_name,
            source_name,
            status
        )
        VALUES (
            'adzuna_job_ingestion',
            'adzuna',
            'STARTED'
        )
        RETURNING batch_id;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            batch_id = cursor.fetchone()[0]

        connection.commit()

    return batch_id


def update_ingestion_batch(
    *,
    batch_id: UUID,
    status: str,
    records_received: int,
    records_loaded: int,
    records_quarantined: int,
    api_requests_made: int,
    api_success_count: int,
    api_failure_count: int,
    api_rate_limit_hit: bool = False,
    error_message: str | None = None,
    failure_type: str | None = None,
    is_retryable: bool | None = None,
) -> None:
    """
    Update an ingestion batch after the ingestion attempt finishes.

    Args:
        batch_id: Batch to update.
        status: STARTED, SUCCESS, FAILED, or PARTIAL.
        records_received: Number of raw job payloads received from the API.
        records_loaded: Number of valid jobs inserted.
        records_quarantined: Number of invalid jobs quarantined.
        api_requests_made: Number of API calls attempted.
        api_success_count: Number of successful API calls.
        api_failure_count: Number of failed API calls.
        api_rate_limit_hit: Whether a rate-limit response was detected.
        error_message: Optional error message.
        failure_type: Optional failure category.
        is_retryable: Whether the failure is retryable.
    """

    query = """
        UPDATE raw.ingestion_batches
        SET
            status = %(status)s,
            finished_at = NOW(),
            records_received = %(records_received)s,
            records_loaded = %(records_loaded)s,
            records_quarantined = %(records_quarantined)s,
            api_requests_made = %(api_requests_made)s,
            api_success_count = %(api_success_count)s,
            api_failure_count = %(api_failure_count)s,
            api_rate_limit_hit = %(api_rate_limit_hit)s,
            error_message = %(error_message)s,
            failure_type = %(failure_type)s,
            is_retryable = %(is_retryable)s,
            updated_at = NOW()
        WHERE batch_id = %(batch_id)s;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                {
                    "batch_id": batch_id,
                    "status": status,
                    "records_received": records_received,
                    "records_loaded": records_loaded,
                    "records_quarantined": records_quarantined,
                    "api_requests_made": api_requests_made,
                    "api_success_count": api_success_count,
                    "api_failure_count": api_failure_count,
                    "api_rate_limit_hit": api_rate_limit_hit,
                    "error_message": error_message,
                    "failure_type": failure_type,
                    "is_retryable": is_retryable,
                },
            )

        connection.commit()


def get_active_adzuna_query_configs() -> list[AdzunaQueryConfig]:
    """
    Read active Adzuna query configurations from the database.

    Returns:
        list[AdzunaQueryConfig]: Active query configurations.
    """

    query = """
        SELECT
            query_config_id,
            country_code,
            keyword,
            location,
            results_per_page,
            max_pages
        FROM raw.adzuna_query_config
        WHERE is_active = TRUE
        ORDER BY query_config_id;
    """

    with get_connection() as connection:
        with connection.cursor(row_factory=dict_row) as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    return [
        AdzunaQueryConfig(
            query_config_id=row["query_config_id"],
            country_code=row["country_code"],
            keyword=row["keyword"],
            location=row["location"],
            results_per_page=row["results_per_page"],
            max_pages=row["max_pages"],
        )
        for row in rows
    ]


def insert_api_response(
    *,
    batch_id: UUID,
    query_config: AdzunaQueryConfig,
    page_number: int,
    request_url_hash: str,
    request_params: dict[str, Any],
    response_status_code: int,
    records_returned: int,
    total_count: int | None,
    raw_response_json: dict[str, Any],
) -> UUID:
    """
    Insert one Adzuna API response/page into raw.adzuna_api_responses.

    Returns:
        UUID: Inserted api_response_id.
    """

    query = """
        INSERT INTO raw.adzuna_api_responses (
            batch_id,
            query_config_id,
            country_code,
            keyword,
            location,
            page_number,
            results_per_page,
            request_url_hash,
            request_params_json,
            response_status_code,
            records_returned,
            total_count,
            raw_response_json
        )
        VALUES (
            %(batch_id)s,
            %(query_config_id)s,
            %(country_code)s,
            %(keyword)s,
            %(location)s,
            %(page_number)s,
            %(results_per_page)s,
            %(request_url_hash)s,
            %(request_params_json)s,
            %(response_status_code)s,
            %(records_returned)s,
            %(total_count)s,
            %(raw_response_json)s
        )
        RETURNING api_response_id;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                {
                    "batch_id": batch_id,
                    "query_config_id": query_config.query_config_id,
                    "country_code": query_config.country_code,
                    "keyword": query_config.keyword,
                    "location": query_config.location,
                    "page_number": page_number,
                    "results_per_page": query_config.results_per_page,
                    "request_url_hash": request_url_hash,
                    "request_params_json": Jsonb(request_params),
                    "response_status_code": response_status_code,
                    "records_returned": records_returned,
                    "total_count": total_count,
                    "raw_response_json": Jsonb(raw_response_json),
                },
            )

            api_response_id = cursor.fetchone()[0]

        connection.commit()

    return api_response_id


def insert_source_adzuna_job(job_row: dict[str, Any]) -> None:
    """
    Insert one valid Adzuna job observation.

    Args:
        job_row: Normalized job fields prepared by the ingestion loader.
    """

    query = """
        INSERT INTO raw.source_adzuna_jobs (
            api_response_id,
            batch_id,
            query_config_id,
            adzuna_job_id,
            title,
            company_name,
            location_text,
            description_text,
            redirect_url,
            source_created_at,
            salary_min,
            salary_max,
            salary_is_predicted,
            category_label,
            category_tag,
            contract_time,
            contract_type,
            latitude,
            longitude,
            country_code,
            search_keyword,
            search_location,
            record_hash,
            raw_payload
        )
        VALUES (
            %(api_response_id)s,
            %(batch_id)s,
            %(query_config_id)s,
            %(adzuna_job_id)s,
            %(title)s,
            %(company_name)s,
            %(location_text)s,
            %(description_text)s,
            %(redirect_url)s,
            %(source_created_at)s,
            %(salary_min)s,
            %(salary_max)s,
            %(salary_is_predicted)s,
            %(category_label)s,
            %(category_tag)s,
            %(contract_time)s,
            %(contract_type)s,
            %(latitude)s,
            %(longitude)s,
            %(country_code)s,
            %(search_keyword)s,
            %(search_location)s,
            %(record_hash)s,
            %(raw_payload)s
        );
    """

    payload = dict(job_row)
    payload["raw_payload"] = Jsonb(payload["raw_payload"])

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, payload)

        connection.commit()


def insert_quarantined_record(
    *,
    batch_id: UUID,
    api_response_id: UUID | None,
    query_config_id: int | None,
    failure_stage: str,
    failure_reason: str,
    raw_payload: dict[str, Any],
) -> None:
    """
    Insert a failed record into raw.quarantined_records.

    Quarantining allows the pipeline to keep loading good records while
    preserving bad records for later inspection.
    """

    query = """
        INSERT INTO raw.quarantined_records (
            batch_id,
            api_response_id,
            query_config_id,
            failure_stage,
            failure_reason,
            raw_payload
        )
        VALUES (
            %(batch_id)s,
            %(api_response_id)s,
            %(query_config_id)s,
            %(failure_stage)s,
            %(failure_reason)s,
            %(raw_payload)s
        );
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                {
                    "batch_id": batch_id,
                    "api_response_id": api_response_id,
                    "query_config_id": query_config_id,
                    "failure_stage": failure_stage,
                    "failure_reason": failure_reason,
                    "raw_payload": Jsonb(raw_payload),
                },
            )

        connection.commit()


def upsert_source_collection_state(
    *,
    query_config: AdzunaQueryConfig,
    last_successful_page: int,
    last_record_created_at: str | None,
    last_batch_id: UUID,
) -> None:
    """
    Update source collection state for one query configuration.

    This is the first step toward incremental collection. Sprint 2 only records
    state; later sprints can use it to make smarter collection decisions.
    """

    query = """
        INSERT INTO ops.source_collection_state (
            source_name,
            query_config_id,
            last_successful_run_at,
            last_successful_page,
            last_record_created_at,
            last_batch_id,
            updated_at
        )
        VALUES (
            'adzuna',
            %(query_config_id)s,
            NOW(),
            %(last_successful_page)s,
            %(last_record_created_at)s,
            %(last_batch_id)s,
            NOW()
        )
        ON CONFLICT (source_name, query_config_id)
        DO UPDATE SET
            last_successful_run_at = EXCLUDED.last_successful_run_at,
            last_successful_page = EXCLUDED.last_successful_page,
            last_record_created_at = EXCLUDED.last_record_created_at,
            last_batch_id = EXCLUDED.last_batch_id,
            updated_at = NOW();
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                {
                    "query_config_id": query_config.query_config_id,
                    "last_successful_page": last_successful_page,
                    "last_record_created_at": last_record_created_at,
                    "last_batch_id": last_batch_id,
                },
            )

        connection.commit()


def record_ingestion_retry(
    *,
    batch_id: UUID,
    retry_count: int,
    max_retries: int,
    next_retry_at: str | None,
    error_message: str,
    failure_type: str,
    api_rate_limit_hit: bool,
) -> None:
    """
    Record retry metadata on the active ingestion batch.

    This makes retries visible in raw.ingestion_batches while the batch is still
    running. If the process crashes during retry attempts, we still have useful
    metadata for debugging.

    Args:
        batch_id: Active ingestion batch.
        retry_count: Number of retry attempts already made.
        max_retries: Maximum allowed retries.
        next_retry_at: Timestamp when the next retry is planned.
        error_message: Most recent retryable error.
        failure_type: Exception class name.
        api_rate_limit_hit: Whether the retry was caused by rate limiting.
    """

    query = """
        UPDATE raw.ingestion_batches
        SET
            retry_count = %(retry_count)s,
            max_retries = %(max_retries)s,
            last_retry_at = NOW(),
            next_retry_at = %(next_retry_at)s,
            error_message = %(error_message)s,
            failure_type = %(failure_type)s,
            is_retryable = TRUE,
            api_rate_limit_hit = api_rate_limit_hit OR %(api_rate_limit_hit)s,
            updated_at = NOW()
        WHERE batch_id = %(batch_id)s;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                {
                    "batch_id": batch_id,
                    "retry_count": retry_count,
                    "max_retries": max_retries,
                    "next_retry_at": next_retry_at,
                    "error_message": error_message,
                    "failure_type": failure_type,
                    "api_rate_limit_hit": api_rate_limit_hit,
                },
            )

        connection.commit()


def create_pipeline_run(
    *,
    pipeline_name: str,
    trigger_type: str,
    git_sha: str | None,
) -> tuple[UUID, str]:
    """
    Create a new ops.pipeline_runs row.

    Args:
        pipeline_name: Name of the end-to-end pipeline.
        trigger_type: manual, scheduled, or ci.
        git_sha: Current git commit SHA if available.

    Returns:
        tuple[UUID, str]: pipeline_run_id and started_at timestamp as ISO text.
    """

    query = """
        INSERT INTO ops.pipeline_runs (
            pipeline_name,
            started_at,
            status,
            trigger_type,
            git_sha
        )
        VALUES (
            %(pipeline_name)s,
            NOW(),
            'STARTED',
            %(trigger_type)s,
            %(git_sha)s
        )
        RETURNING
            pipeline_run_id,
            started_at;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                {
                    "pipeline_name": pipeline_name,
                    "trigger_type": trigger_type,
                    "git_sha": git_sha,
                },
            )
            row = cursor.fetchone()

        connection.commit()

    if row is None:
        raise RuntimeError("Failed to create pipeline run.")

    return row[0], row[1].isoformat()


def update_pipeline_run(
    *,
    pipeline_run_id: UUID,
    status: str,
    ingestion_batch_id: UUID | None,
    dbt_invocation_id: str | None,
    dbt_status: str | None,
    tests_passed: int,
    tests_failed: int,
    error_message: str | None,
) -> None:
    """
    Update an ops.pipeline_runs row after pipeline execution.

    Args:
        pipeline_run_id: Pipeline run to update.
        status: Final pipeline status.
        ingestion_batch_id: Linked ingestion batch if available.
        dbt_invocation_id: dbt invocation ID from run_results.json.
        dbt_status: dbt execution status.
        tests_passed: Number of dbt tests that passed.
        tests_failed: Number of dbt tests that failed or errored.
        error_message: Failure message if the pipeline failed.
    """

    query = """
        UPDATE ops.pipeline_runs
        SET
            finished_at = NOW(),
            status = %(status)s,
            ingestion_batch_id = %(ingestion_batch_id)s,
            dbt_invocation_id = %(dbt_invocation_id)s,
            dbt_status = %(dbt_status)s,
            tests_passed = %(tests_passed)s,
            tests_failed = %(tests_failed)s,
            error_message = %(error_message)s,
            updated_at = NOW()
        WHERE pipeline_run_id = %(pipeline_run_id)s;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                {
                    "pipeline_run_id": pipeline_run_id,
                    "status": status,
                    "ingestion_batch_id": ingestion_batch_id,
                    "dbt_invocation_id": dbt_invocation_id,
                    "dbt_status": dbt_status,
                    "tests_passed": tests_passed,
                    "tests_failed": tests_failed,
                    "error_message": error_message,
                },
            )

        connection.commit()


def get_latest_ingestion_batch_after(started_at: str) -> UUID | None:
    """
    Find the latest Adzuna ingestion batch started after a pipeline started.

    Args:
        started_at: Pipeline start timestamp.

    Returns:
        UUID | None: Latest batch ID if found.
    """

    query = """
        SELECT batch_id
        FROM raw.ingestion_batches
        WHERE source_name = 'adzuna'
          AND started_at >= %(started_at)s
        ORDER BY started_at DESC
        LIMIT 1;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, {"started_at": started_at})
            row = cursor.fetchone()

    if row is None:
        return None

    return row[0]


def get_ingestion_batch_summary(batch_id: UUID) -> dict | None:
    """
    Fetch summary information for one ingestion batch.

    Args:
        batch_id: Ingestion batch ID.

    Returns:
        dict | None: Batch summary, or None if the batch does not exist.
    """

    query = """
        SELECT
            batch_id,
            status,
            started_at,
            finished_at,
            records_received,
            records_loaded,
            records_quarantined,
            api_requests_made,
            api_success_count,
            api_failure_count,
            api_rate_limit_hit,
            failure_type,
            error_message
        FROM raw.ingestion_batches
        WHERE batch_id = %(batch_id)s;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, {"batch_id": batch_id})
            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "batch_id": row[0],
        "status": row[1],
        "started_at": row[2],
        "finished_at": row[3],
        "records_received": row[4],
        "records_loaded": row[5],
        "records_quarantined": row[6],
        "api_requests_made": row[7],
        "api_success_count": row[8],
        "api_failure_count": row[9],
        "api_rate_limit_hit": row[10],
        "failure_type": row[11],
        "error_message": row[12],
    }


def mark_pipeline_run_failed(
    *,
    pipeline_run_id: UUID,
    ingestion_batch_id: UUID | None,
    dbt_invocation_id: str | None,
    dbt_status: str | None,
    tests_passed: int,
    tests_failed: int,
    error_message: str,
) -> None:
    """
    Convenience wrapper for marking a pipeline run as FAILED.
    """

    update_pipeline_run(
        pipeline_run_id=pipeline_run_id,
        status="FAILED",
        ingestion_batch_id=ingestion_batch_id,
        dbt_invocation_id=dbt_invocation_id,
        dbt_status=dbt_status,
        tests_passed=tests_passed,
        tests_failed=tests_failed,
        error_message=error_message,
    )


def mark_pipeline_run_success(
    *,
    pipeline_run_id: UUID,
    ingestion_batch_id: UUID | None,
    dbt_invocation_id: str | None,
    tests_passed: int,
    tests_failed: int,
) -> None:
    """
    Convenience wrapper for marking a pipeline run as SUCCESS.
    """

    update_pipeline_run(
        pipeline_run_id=pipeline_run_id,
        status="SUCCESS",
        ingestion_batch_id=ingestion_batch_id,
        dbt_invocation_id=dbt_invocation_id,
        dbt_status="SUCCESS",
        tests_passed=tests_passed,
        tests_failed=tests_failed,
        error_message=None,
    )