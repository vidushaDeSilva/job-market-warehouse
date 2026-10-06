"""
check_sprint2.py

Validates the Sprint 2 Adzuna ingestion output.

The script checks that:
1. A successful or partial ingestion batch exists
2. At least one API response has been stored
3. At least one Adzuna job observation has been loaded
4. Source collection state has been updated

It does not modify the database.
"""

from rich.console import Console
from rich.panel import Panel

from job_market.db import get_connection


console = Console()


def fetch_counts() -> dict[str, int]:
    """
    Fetch Sprint 2 validation counts from PostgreSQL.

    Returns:
        dict[str, int]: Counts used to validate ingestion output.
    """

    query = """
        SELECT
            (
                SELECT COUNT(*)
                FROM raw.ingestion_batches
                WHERE source_name = 'adzuna'
                  AND status IN ('SUCCESS', 'PARTIAL')
            ) AS successful_batches,

            (
                SELECT COUNT(*)
                FROM raw.adzuna_api_responses
            ) AS api_responses,

            (
                SELECT COUNT(*)
                FROM raw.source_adzuna_jobs
            ) AS source_jobs,

            (
                SELECT COUNT(*)
                FROM raw.quarantined_records
            ) AS quarantined_records,

            (
                SELECT COUNT(*)
                FROM ops.source_collection_state
                WHERE source_name = 'adzuna'
            ) AS collection_state_rows;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Validation query returned no result.")

    return {
        "successful_batches": row[0],
        "api_responses": row[1],
        "source_jobs": row[2],
        "quarantined_records": row[3],
        "collection_state_rows": row[4],
    }


def main() -> None:
    """
    Validate that Sprint 2 has loaded real Adzuna source data.
    """

    console.print("[bold cyan]Checking Sprint 2 Adzuna ingestion...[/bold cyan]")

    counts = fetch_counts()

    failures = []

    if counts["successful_batches"] == 0:
        failures.append("No SUCCESS or PARTIAL Adzuna ingestion batch found.")

    if counts["api_responses"] == 0:
        failures.append("No rows found in raw.adzuna_api_responses.")

    if counts["source_jobs"] == 0:
        failures.append("No rows found in raw.source_adzuna_jobs.")

    if counts["collection_state_rows"] == 0:
        failures.append("No rows found in ops.source_collection_state.")

    if failures:
        failure_text = "\n".join(f"- {failure}" for failure in failures)

        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 2 validation failed.[/bold red]\n\n"
                    f"{failure_text}\n\n"
                    f"Current counts:\n"
                    f"successful_batches: {counts['successful_batches']}\n"
                    f"api_responses: {counts['api_responses']}\n"
                    f"source_jobs: {counts['source_jobs']}\n"
                    f"quarantined_records: {counts['quarantined_records']}\n"
                    f"collection_state_rows: {counts['collection_state_rows']}"
                ),
                title="Sprint 2 Check",
            )
        )

        raise SystemExit(1)

    console.print(
        Panel.fit(
            (
                "[bold green]Sprint 2 validation passed.[/bold green]\n\n"
                f"Successful/partial batches: {counts['successful_batches']}\n"
                f"API responses stored: {counts['api_responses']}\n"
                f"Source job observations loaded: {counts['source_jobs']}\n"
                f"Quarantined records: {counts['quarantined_records']}\n"
                f"Collection state rows: {counts['collection_state_rows']}"
            ),
            title="Sprint 2 Check",
        )
    )


if __name__ == "__main__":
    main()