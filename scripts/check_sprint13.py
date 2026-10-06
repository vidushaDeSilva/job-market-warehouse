"""
check_sprint13.py

Validates Sprint 13 orchestration.

This script checks:
1. At least one pipeline run exists.
2. Latest pipeline run has a terminal status.
3. Pipeline run links to an ingestion batch.
4. Successful pipeline runs have dbt invocation metadata.
5. Operational health mart exists.

It does not modify the database.
"""

from rich.console import Console
from rich.panel import Panel

from job_market.db import get_connection


console = Console()


def fetch_summary() -> dict:
    """
    Fetch orchestration validation summary.

    Returns:
        dict: Summary values.
    """

    query = """
        WITH latest_pipeline AS (

            SELECT *
            FROM ops.pipeline_runs
            ORDER BY started_at DESC
            LIMIT 1

        )

        SELECT
            (
                SELECT COUNT(*)
                FROM ops.pipeline_runs
            ) AS pipeline_run_count,

            (
                SELECT status
                FROM latest_pipeline
            ) AS latest_status,

            (
                SELECT COUNT(*)
                FROM latest_pipeline
                WHERE status IN ('SUCCESS', 'FAILED', 'PARTIAL')
            ) AS latest_has_terminal_status,

            (
                SELECT COUNT(*)
                FROM latest_pipeline
                WHERE ingestion_batch_id IS NOT NULL
            ) AS latest_has_ingestion_batch,

            (
                SELECT COUNT(*)
                FROM latest_pipeline
                WHERE status = 'SUCCESS'
                  AND dbt_invocation_id IS NOT NULL
            ) AS successful_latest_has_dbt_invocation,

            (
                SELECT COUNT(*)
                FROM dev_marts.mart_pipeline_health
            ) AS pipeline_health_rows,

            (
                SELECT pipeline_health_status
                FROM dev_marts.mart_pipeline_health
                LIMIT 1
            ) AS pipeline_health_status;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Sprint 13 validation query returned no row.")

    return {
        "pipeline_run_count": row[0],
        "latest_status": row[1],
        "latest_has_terminal_status": row[2],
        "latest_has_ingestion_batch": row[3],
        "successful_latest_has_dbt_invocation": row[4],
        "pipeline_health_rows": row[5],
        "pipeline_health_status": row[6],
    }


def main() -> None:
    """
    Validate orchestration state.
    """

    console.print("[bold cyan]Checking Sprint 13 orchestration...[/bold cyan]")

    try:
        summary = fetch_summary()
    except Exception as exc:
        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 13 validation failed.[/bold red]\n\n"
                    "Could not query orchestration metadata.\n"
                    "Run `make orchestrated-pipeline` first.\n\n"
                    f"Error: {exc}"
                ),
                title="Sprint 13 Check",
            )
        )
        raise SystemExit(1) from exc

    failures = []

    if summary["pipeline_run_count"] == 0:
        failures.append("No pipeline runs found.")

    if summary["latest_has_terminal_status"] != 1:
        failures.append("Latest pipeline run does not have a terminal status.")

    if summary["latest_has_ingestion_batch"] != 1:
        failures.append("Latest pipeline run is not linked to an ingestion batch.")

    if (
        summary["latest_status"] == "SUCCESS"
        and summary["successful_latest_has_dbt_invocation"] != 1
    ):
        failures.append("Successful latest run has no dbt invocation ID.")

    if summary["pipeline_health_rows"] != 1:
        failures.append("mart_pipeline_health should contain exactly one row.")

    if failures:
        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 13 validation failed.[/bold red]\n\n"
                    + "\n".join(f"- {failure}" for failure in failures)
                    + f"\n\nSummary:\n{summary}"
                ),
                title="Sprint 13 Check",
            )
        )
        raise SystemExit(1)

    console.print(
        Panel.fit(
            (
                "[bold green]Sprint 13 validation passed.[/bold green]\n\n"
                f"Pipeline runs: {summary['pipeline_run_count']}\n"
                f"Latest status: {summary['latest_status']}\n"
                f"Pipeline health status: {summary['pipeline_health_status']}"
            ),
            title="Sprint 13 Check",
        )
    )


if __name__ == "__main__":
    main()