"""
check_sprint3.py

Validates Sprint 3 reliability-related ingestion metadata.

This script checks whether raw.ingestion_batches contains the fields that
Sprint 3 uses for retry tracking and confirms that recent Adzuna batches have
valid operational counters.

It does not modify the database.
"""

from rich.console import Console
from rich.panel import Panel

from job_market.db import get_connection

console = Console()


def fetch_latest_batch() -> dict | None:
    """
    Fetch the latest Adzuna ingestion batch.

    Returns:
        dict | None: Latest batch metadata, or None if no batch exists.
    """

    query = """
        SELECT
            batch_id,
            status,
            records_received,
            records_loaded,
            records_quarantined,
            api_requests_made,
            api_success_count,
            api_failure_count,
            api_rate_limit_hit,
            retry_count,
            max_retries,
            failure_type,
            is_retryable,
            error_message,
            started_at,
            finished_at
        FROM raw.ingestion_batches
        WHERE source_name = 'adzuna'
        ORDER BY started_at DESC
        LIMIT 1;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()

    if row is None:
        return None

    return {
        "batch_id": row[0],
        "status": row[1],
        "records_received": row[2],
        "records_loaded": row[3],
        "records_quarantined": row[4],
        "api_requests_made": row[5],
        "api_success_count": row[6],
        "api_failure_count": row[7],
        "api_rate_limit_hit": row[8],
        "retry_count": row[9],
        "max_retries": row[10],
        "failure_type": row[11],
        "is_retryable": row[12],
        "error_message": row[13],
        "started_at": row[14],
        "finished_at": row[15],
    }


def main() -> None:
    """
    Validate Sprint 3 ingestion-hardening metadata.
    """

    console.print("[bold cyan]Checking Sprint 3 ingestion hardening...[/bold cyan]")

    latest_batch = fetch_latest_batch()

    if latest_batch is None:
        console.print(
            Panel.fit(
                "[bold red]No Adzuna ingestion batch found.[/bold red]\n\n"
                "Run `make ingest-adzuna` first.",
                title="Sprint 3 Check",
            )
        )
        raise SystemExit(1)

    failures = []

    if latest_batch["status"] not in {"SUCCESS", "PARTIAL", "FAILED"}:
        failures.append(f"Unexpected batch status: {latest_batch['status']}")

    if latest_batch["finished_at"] is None:
        failures.append("Latest batch does not have finished_at set.")

    if latest_batch["api_requests_made"] < latest_batch["api_success_count"]:
        failures.append("api_requests_made is less than api_success_count.")

    if latest_batch["api_requests_made"] < latest_batch["api_failure_count"]:
        failures.append("api_requests_made is less than api_failure_count.")

    if latest_batch["retry_count"] > latest_batch["max_retries"]:
        failures.append("retry_count is greater than max_retries.")

    if failures:
        failure_text = "\n".join(f"- {failure}" for failure in failures)

        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 3 validation failed.[/bold red]\n\n"
                    f"{failure_text}\n\n"
                    f"Latest batch: {latest_batch}"
                ),
                title="Sprint 3 Check",
            )
        )

        raise SystemExit(1)

    console.print(
        Panel.fit(
            (
                "[bold green]Sprint 3 validation passed.[/bold green]\n\n"
                f"Batch ID: {latest_batch['batch_id']}\n"
                f"Status: {latest_batch['status']}\n"
                f"Records loaded: {latest_batch['records_loaded']}\n"
                f"API requests made: {latest_batch['api_requests_made']}\n"
                f"API failures: {latest_batch['api_failure_count']}\n"
                f"Retries performed: {latest_batch['retry_count']}\n"
                f"Rate limit hit: {latest_batch['api_rate_limit_hit']}\n"
                f"Failure type: {latest_batch['failure_type']}\n"
                f"Retryable failure: {latest_batch['is_retryable']}"
            ),
            title="Sprint 3 Check",
        )
    )


if __name__ == "__main__":
    main()
