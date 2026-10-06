"""
adzuna_loader.py

Production-safer Adzuna ingestion workflow for Sprint 3.

This loader:
1. Creates an ingestion batch
2. Reads active query configurations
3. Calls the Adzuna API page by page
4. Retries only retryable API/network failures
5. Uses exponential backoff between retries
6. Stores full API responses in raw.adzuna_api_responses
7. Stores valid job observations in raw.source_adzuna_jobs
8. Stores invalid job records in raw.quarantined_records
9. Updates raw.ingestion_batches with success/failure/retry metadata
10. Updates ops.source_collection_state after successful query collection

This sprint hardens ingestion but still does not run dbt transformations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
import time
from typing import Any
from uuid import UUID

from rich.console import Console

from job_market.adzuna.client import AdzunaClient, AdzunaSearchRequest, AdzunaSearchResponse
from job_market.config import get_settings
from job_market.errors import (
    AdzunaError,
    AdzunaNonRetryableError,
    AdzunaRateLimitError,
    AdzunaResponseFormatError,
    AdzunaRetryableError,
)
from job_market.repository import (
    AdzunaQueryConfig,
    create_ingestion_batch,
    get_active_adzuna_query_configs,
    insert_api_response,
    insert_quarantined_record,
    insert_source_adzuna_job,
    record_ingestion_retry,
    update_ingestion_batch,
    upsert_source_collection_state,
)
from job_market.utils import sha256_json, sha256_text, utc_now


console = Console()


@dataclass
class IngestionStats:
    """
    Runtime counters for one ingestion batch.
    """

    records_received: int = 0
    records_loaded: int = 0
    records_quarantined: int = 0

    api_requests_made: int = 0
    api_success_count: int = 0
    api_failure_count: int = 0
    api_rate_limit_hit: bool = False

    retry_count: int = 0


def get_nested_value(payload: dict[str, Any], *keys: str) -> Any:
    """
    Safely read a nested value from a dictionary.
    """

    current: Any = payload

    for key in keys:
        if not isinstance(current, dict):
            return None

        current = current.get(key)

    return current


def normalize_text(value: Any) -> str | None:
    """
    Normalize text fields from the Adzuna payload.

    Empty strings are converted to None so validation can treat them as missing.
    """

    if value is None:
        return None

    text = str(value).strip()

    if not text:
        return None

    return text


def normalize_number(value: Any) -> float | None:
    """
    Convert source numeric values to floats when possible.

    If conversion fails, return None instead of crashing the whole ingestion.
    """

    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def build_job_record(
    *,
    batch_id: UUID,
    api_response_id: UUID,
    query_config: AdzunaQueryConfig,
    job_payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Convert one raw Adzuna job payload into a database-ready job row.

    Raises:
        ValueError: If required fields are missing.
    """

    adzuna_job_id = normalize_text(job_payload.get("id"))
    title = normalize_text(job_payload.get("title"))
    company_name = normalize_text(get_nested_value(job_payload, "company", "display_name"))
    description_text = normalize_text(job_payload.get("description"))

    redirect_url = normalize_text(job_payload.get("redirect_url"))
    location_text = normalize_text(get_nested_value(job_payload, "location", "display_name"))

    if not title:
        raise ValueError("Missing required field: title")

    if not company_name:
        raise ValueError("Missing required field: company.display_name")

    if not description_text:
        raise ValueError("Missing required field: description")

    if not adzuna_job_id and not redirect_url:
        raise ValueError("Missing both id and redirect_url; cannot identify job observation")

    source_created_at = normalize_text(job_payload.get("created"))

    salary_min = normalize_number(job_payload.get("salary_min"))
    salary_max = normalize_number(job_payload.get("salary_max"))

    category_label = normalize_text(get_nested_value(job_payload, "category", "label"))
    category_tag = normalize_text(get_nested_value(job_payload, "category", "tag"))

    contract_time = normalize_text(job_payload.get("contract_time"))
    contract_type = normalize_text(job_payload.get("contract_type"))

    latitude = normalize_number(job_payload.get("latitude"))
    longitude = normalize_number(job_payload.get("longitude"))

    record_identity = {
        "adzuna_job_id": adzuna_job_id,
        "redirect_url": redirect_url,
        "title": title,
        "company_name": company_name,
        "location_text": location_text,
        "source_created_at": source_created_at,
    }

    return {
        "api_response_id": api_response_id,
        "batch_id": batch_id,
        "query_config_id": query_config.query_config_id,
        "adzuna_job_id": adzuna_job_id,
        "title": title,
        "company_name": company_name,
        "location_text": location_text,
        "description_text": description_text,
        "redirect_url": redirect_url,
        "source_created_at": source_created_at,
        "salary_min": salary_min,
        "salary_max": salary_max,
        "salary_is_predicted": normalize_text(job_payload.get("salary_is_predicted")),
        "category_label": category_label,
        "category_tag": category_tag,
        "contract_time": contract_time,
        "contract_type": contract_type,
        "latitude": latitude,
        "longitude": longitude,
        "country_code": query_config.country_code,
        "search_keyword": query_config.keyword,
        "search_location": query_config.location,
        "record_hash": sha256_json(record_identity),
        "raw_payload": job_payload,
    }


def extract_jobs_from_response(response_json: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Extract job payloads from an Adzuna API response.

    Adzuna returns jobs under the "results" key.
    """

    results = response_json.get("results", [])

    if not isinstance(results, list):
        raise AdzunaResponseFormatError("Adzuna response field 'results' is not a list.")

    return results


def get_latest_source_created_at(job_rows: list[dict[str, Any]]) -> str | None:
    """
    Return the latest source_created_at value from loaded job rows.
    """

    values = [
        row["source_created_at"]
        for row in job_rows
        if row.get("source_created_at")
    ]

    if not values:
        return None

    return max(values)


def calculate_backoff_seconds(
    *,
    attempt_number: int,
    initial_seconds: float,
    max_seconds: float,
) -> float:
    """
    Calculate exponential backoff delay.

    Example:
        attempt 1 -> 5 seconds
        attempt 2 -> 10 seconds
        attempt 3 -> 20 seconds

    The delay is capped by max_seconds.
    """

    delay = initial_seconds * (2 ** max(attempt_number - 1, 0))

    return min(delay, max_seconds)


def call_adzuna_with_retries(
    *,
    client: AdzunaClient,
    request: AdzunaSearchRequest,
    batch_id: UUID,
    stats: IngestionStats,
) -> AdzunaSearchResponse:
    """
    Call the Adzuna API with retry handling.

    Retryable failures:
        - timeout
        - network error
        - HTTP 429
        - HTTP 500/502/503/504

    Non-retryable failures:
        - invalid credentials
        - bad request
        - unsupported configuration
        - other HTTP 4xx except 429

    Args:
        client: Adzuna API client.
        request: Search request.
        batch_id: Active ingestion batch.
        stats: Runtime counters.

    Returns:
        AdzunaSearchResponse: Successful API response.

    Raises:
        AdzunaError: If all retries fail or a non-retryable error occurs.
    """

    settings = get_settings()
    max_retries = settings.adzuna_max_retries

    attempt_number = 0

    while True:
        attempt_number += 1
        stats.api_requests_made += 1

        try:
            response = client.search_jobs(request)
            stats.api_success_count += 1

            return response

        except AdzunaRateLimitError as exc:
            stats.api_failure_count += 1
            stats.api_rate_limit_hit = True

            if attempt_number > max_retries + 1:
                raise

            retry_delay = calculate_backoff_seconds(
                attempt_number=attempt_number,
                initial_seconds=settings.adzuna_retry_backoff_initial_seconds,
                max_seconds=settings.adzuna_retry_backoff_max_seconds,
            )

            next_retry_at = utc_now() + timedelta(seconds=retry_delay)
            stats.retry_count += 1

            record_ingestion_retry(
                batch_id=batch_id,
                retry_count=stats.retry_count,
                max_retries=max_retries,
                next_retry_at=next_retry_at.isoformat(),
                error_message=str(exc),
                failure_type=type(exc).__name__,
                api_rate_limit_hit=True,
            )

            console.print(
                (
                    f"[yellow]Rate limit hit. Retrying in {retry_delay:.1f} seconds "
                    f"({stats.retry_count}/{max_retries}).[/yellow]"
                )
            )

            time.sleep(retry_delay)

        except AdzunaRetryableError as exc:
            stats.api_failure_count += 1

            if attempt_number > max_retries + 1:
                raise

            retry_delay = calculate_backoff_seconds(
                attempt_number=attempt_number,
                initial_seconds=settings.adzuna_retry_backoff_initial_seconds,
                max_seconds=settings.adzuna_retry_backoff_max_seconds,
            )

            next_retry_at = utc_now() + timedelta(seconds=retry_delay)
            stats.retry_count += 1

            record_ingestion_retry(
                batch_id=batch_id,
                retry_count=stats.retry_count,
                max_retries=max_retries,
                next_retry_at=next_retry_at.isoformat(),
                error_message=str(exc),
                failure_type=type(exc).__name__,
                api_rate_limit_hit=False,
            )

            console.print(
                (
                    f"[yellow]Retryable Adzuna error: {exc}. "
                    f"Retrying in {retry_delay:.1f} seconds "
                    f"({stats.retry_count}/{max_retries}).[/yellow]"
                )
            )

            time.sleep(retry_delay)

        except AdzunaNonRetryableError:
            stats.api_failure_count += 1
            raise

        except AdzunaError:
            stats.api_failure_count += 1
            raise


def ingest_query_config(
    *,
    client: AdzunaClient,
    batch_id: UUID,
    query_config: AdzunaQueryConfig,
    stats: IngestionStats,
) -> None:
    """
    Ingest all configured pages for one Adzuna query configuration.

    Args:
        client: Adzuna API client.
        batch_id: Active ingestion batch ID.
        query_config: Query configuration to execute.
        stats: Mutable runtime counters.
    """

    settings = get_settings()

    console.print(
        (
            f"[cyan]Query[/cyan] {query_config.query_config_id}: "
            f"{query_config.keyword!r}, {query_config.location!r}, "
            f"{query_config.country_code.upper()}"
        )
    )

    latest_loaded_rows: list[dict[str, Any]] = []
    last_successful_page = 0

    for page_number in range(1, query_config.max_pages + 1):
        request = AdzunaSearchRequest(
            country_code=query_config.country_code,
            page_number=page_number,
            keyword=query_config.keyword,
            location=query_config.location,
            results_per_page=query_config.results_per_page,
        )

        console.print(f"  Fetching page {page_number}...")

        response = call_adzuna_with_retries(
            client=client,
            request=request,
            batch_id=batch_id,
            stats=stats,
        )

        response_json = response.response_json
        jobs = extract_jobs_from_response(response_json)

        stats.records_received += len(jobs)

        request_hash = sha256_text(response.request_url)

        api_response_id = insert_api_response(
            batch_id=batch_id,
            query_config=query_config,
            page_number=page_number,
            request_url_hash=request_hash,
            request_params=response.safe_request_params,
            response_status_code=response.status_code,
            records_returned=len(jobs),
            total_count=response_json.get("count"),
            raw_response_json=response_json,
        )

        loaded_this_page = 0
        quarantined_this_page = 0

        for job_payload in jobs:
            try:
                job_row = build_job_record(
                    batch_id=batch_id,
                    api_response_id=api_response_id,
                    query_config=query_config,
                    job_payload=job_payload,
                )

                insert_source_adzuna_job(job_row)
                latest_loaded_rows.append(job_row)

                stats.records_loaded += 1
                loaded_this_page += 1

            except Exception as exc:
                insert_quarantined_record(
                    batch_id=batch_id,
                    api_response_id=api_response_id,
                    query_config_id=query_config.query_config_id,
                    failure_stage="job_payload_validation",
                    failure_reason=str(exc),
                    raw_payload=job_payload,
                )

                stats.records_quarantined += 1
                quarantined_this_page += 1

        last_successful_page = page_number

        console.print(
            (
                f"  Loaded {loaded_this_page} jobs, "
                f"quarantined {quarantined_this_page} jobs"
            )
        )

        if len(jobs) == 0:
            console.print("  No jobs returned. Stopping this query early.")
            break

        # Be polite to the API and reduce risk of hitting rate limits.
        if settings.adzuna_request_pause_seconds > 0:
            time.sleep(settings.adzuna_request_pause_seconds)

    if last_successful_page > 0:
        upsert_source_collection_state(
            query_config=query_config,
            last_successful_page=last_successful_page,
            last_record_created_at=get_latest_source_created_at(latest_loaded_rows),
            last_batch_id=batch_id,
        )


def classify_final_status(stats: IngestionStats) -> str:
    """
    Determine final batch status based on loaded and quarantined records.

    Returns:
        str: SUCCESS, PARTIAL, or FAILED.
    """

    if stats.records_loaded > 0 and stats.records_quarantined == 0:
        return "SUCCESS"

    if stats.records_loaded > 0 and stats.records_quarantined > 0:
        return "PARTIAL"

    return "FAILED"


def run_adzuna_ingestion() -> None:
    """
    Run the Sprint 3 Adzuna ingestion pipeline.
    """

    console.print("[bold cyan]Starting Adzuna ingestion...[/bold cyan]")

    query_configs = get_active_adzuna_query_configs()

    if not query_configs:
        raise RuntimeError("No active Adzuna query configurations found.")

    settings = get_settings()
    batch_id = create_ingestion_batch()
    stats = IngestionStats()

    console.print(f"Created ingestion batch: [bold]{batch_id}[/bold]")
    console.print(
        (
            f"Retry policy: max_retries={settings.adzuna_max_retries}, "
            f"initial_backoff={settings.adzuna_retry_backoff_initial_seconds}s, "
            f"max_backoff={settings.adzuna_retry_backoff_max_seconds}s\n"
        )
    )

    try:
        client = AdzunaClient()

        for query_config in query_configs:
            ingest_query_config(
                client=client,
                batch_id=batch_id,
                query_config=query_config,
                stats=stats,
            )

        final_status = classify_final_status(stats)

        update_ingestion_batch(
            batch_id=batch_id,
            status=final_status,
            records_received=stats.records_received,
            records_loaded=stats.records_loaded,
            records_quarantined=stats.records_quarantined,
            api_requests_made=stats.api_requests_made,
            api_success_count=stats.api_success_count,
            api_failure_count=stats.api_failure_count,
            api_rate_limit_hit=stats.api_rate_limit_hit,
        )

        console.print(
            (
                "\n[bold green]Adzuna ingestion completed.[/bold green]\n"
                f"Batch status: {final_status}\n"
                f"Records received: {stats.records_received}\n"
                f"Records loaded: {stats.records_loaded}\n"
                f"Records quarantined: {stats.records_quarantined}\n"
                f"API requests made: {stats.api_requests_made}\n"
                f"API failures: {stats.api_failure_count}\n"
                f"Retries performed: {stats.retry_count}\n"
                f"Rate limit hit: {stats.api_rate_limit_hit}"
            )
        )

        if final_status == "FAILED":
            raise RuntimeError("Ingestion finished but no records were loaded.")

    except AdzunaNonRetryableError as exc:
        update_ingestion_batch(
            batch_id=batch_id,
            status="FAILED",
            records_received=stats.records_received,
            records_loaded=stats.records_loaded,
            records_quarantined=stats.records_quarantined,
            api_requests_made=stats.api_requests_made,
            api_success_count=stats.api_success_count,
            api_failure_count=stats.api_failure_count,
            api_rate_limit_hit=stats.api_rate_limit_hit,
            error_message=str(exc),
            failure_type=type(exc).__name__,
            is_retryable=False,
        )

        console.print(f"\n[bold red]Non-retryable Adzuna error:[/bold red] {exc}")
        raise

    except AdzunaRetryableError as exc:
        update_ingestion_batch(
            batch_id=batch_id,
            status="FAILED",
            records_received=stats.records_received,
            records_loaded=stats.records_loaded,
            records_quarantined=stats.records_quarantined,
            api_requests_made=stats.api_requests_made,
            api_success_count=stats.api_success_count,
            api_failure_count=stats.api_failure_count,
            api_rate_limit_hit=stats.api_rate_limit_hit,
            error_message=str(exc),
            failure_type=type(exc).__name__,
            is_retryable=True,
        )

        console.print(
            f"\n[bold red]Retryable Adzuna error remained after retries:[/bold red] {exc}"
        )
        raise

    except Exception as exc:
        update_ingestion_batch(
            batch_id=batch_id,
            status="FAILED",
            records_received=stats.records_received,
            records_loaded=stats.records_loaded,
            records_quarantined=stats.records_quarantined,
            api_requests_made=stats.api_requests_made,
            api_success_count=stats.api_success_count,
            api_failure_count=stats.api_failure_count,
            api_rate_limit_hit=stats.api_rate_limit_hit,
            error_message=str(exc),
            failure_type=type(exc).__name__,
            is_retryable=None,
        )

        console.print(f"\n[bold red]Adzuna ingestion failed:[/bold red] {exc}")
        raise