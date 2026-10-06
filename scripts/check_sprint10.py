"""
check_sprint10.py

Validates Sprint 10 observability and data quality marts.

This script checks:
1. Observability marts exist and contain rows.
2. Pipeline health has exactly one row.
3. Data quality summary has exactly one row.
4. Pipeline runs are being tracked.
5. Share/rate metrics are valid.

It does not modify the database.
"""

from rich.console import Console
from rich.panel import Panel

from job_market.db import get_connection


console = Console()


def fetch_counts() -> dict[str, int | str | None]:
    """
    Fetch Sprint 10 validation metrics.

    Returns:
        dict[str, int | str | None]: Validation metrics.
    """

    query = """
        SELECT
            (
                SELECT COUNT(*)
                FROM ops.pipeline_runs
            ) AS pipeline_run_count,

            (
                SELECT COUNT(*)
                FROM dev_marts.mart_pipeline_health
            ) AS pipeline_health_rows,

            (
                SELECT pipeline_health_status
                FROM dev_marts.mart_pipeline_health
                LIMIT 1
            ) AS pipeline_health_status,

            (
                SELECT COUNT(*)
                FROM dev_marts.mart_ingestion_batch_summary
            ) AS ingestion_batch_summary_rows,

            (
                SELECT COUNT(*)
                FROM dev_marts.mart_api_request_summary
            ) AS api_request_summary_rows,

            (
                SELECT COUNT(*)
                FROM dev_marts.mart_data_quality_summary
            ) AS data_quality_summary_rows,

            (
                SELECT COUNT(*)
                FROM dev_marts.mart_data_quality_summary
                WHERE duplicate_percentage < 0
                   OR duplicate_percentage > 1
                   OR salary_coverage < 0
                   OR salary_coverage > 1
                   OR skill_extraction_coverage < 0
                   OR skill_extraction_coverage > 1
                   OR unknown_role_share < 0
                   OR unknown_role_share > 1
            ) AS invalid_data_quality_rates,

            (
                SELECT COUNT(*)
                FROM dev_marts.mart_ingestion_batch_summary
                WHERE quarantine_rate < 0
                   OR quarantine_rate > 1
                   OR api_failure_rate < 0
                   OR api_failure_rate > 1
            ) AS invalid_ingestion_rates,

            (
                SELECT COALESCE(SUM(tests_failed), 0)
                FROM ops.pipeline_runs
            ) AS total_dbt_test_failures;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Sprint 10 validation query returned no rows.")

    return {
        "pipeline_run_count": row[0],
        "pipeline_health_rows": row[1],
        "pipeline_health_status": row[2],
        "ingestion_batch_summary_rows": row[3],
        "api_request_summary_rows": row[4],
        "data_quality_summary_rows": row[5],
        "invalid_data_quality_rates": row[6],
        "invalid_ingestion_rates": row[7],
        "total_dbt_test_failures": row[8],
    }


def main() -> None:
    """
    Validate Sprint 10 outputs.
    """

    console.print("[bold cyan]Checking Sprint 10 observability...[/bold cyan]")

    try:
        counts = fetch_counts()
    except Exception as exc:
        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 10 validation failed.[/bold red]\n\n"
                    "Could not query Sprint 10 observability marts.\n"
                    "Run `make observed-pipeline` first.\n\n"
                    f"Error: {exc}"
                ),
                title="Sprint 10 Check",
            )
        )
        raise SystemExit(1) from exc

    failures = []

    if counts["pipeline_run_count"] == 0:
        failures.append("No rows found in ops.pipeline_runs.")

    if counts["pipeline_health_rows"] != 1:
        failures.append("mart_pipeline_health should contain exactly one row.")

    if counts["ingestion_batch_summary_rows"] == 0:
        failures.append("mart_ingestion_batch_summary has no rows.")

    if counts["api_request_summary_rows"] == 0:
        failures.append("mart_api_request_summary has no rows.")

    if counts["data_quality_summary_rows"] != 1:
        failures.append("mart_data_quality_summary should contain exactly one row.")

    if counts["invalid_data_quality_rates"] > 0:
        failures.append("Invalid data quality rate values found.")

    if counts["invalid_ingestion_rates"] > 0:
        failures.append("Invalid ingestion rate values found.")

    if failures:
        failure_text = "\n".join(f"- {failure}" for failure in failures)

        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 10 validation failed.[/bold red]\n\n"
                    f"{failure_text}\n\n"
                    f"Counts:\n{counts}"
                ),
                title="Sprint 10 Check",
            )
        )

        raise SystemExit(1)

    console.print(
        Panel.fit(
            (
                "[bold green]Sprint 10 validation passed.[/bold green]\n\n"
                f"Pipeline runs: {counts['pipeline_run_count']}\n"
                f"Pipeline health rows: {counts['pipeline_health_rows']}\n"
                f"Pipeline health status: {counts['pipeline_health_status']}\n"
                f"Ingestion batch summary rows: {counts['ingestion_batch_summary_rows']}\n"
                f"API request summary rows: {counts['api_request_summary_rows']}\n"
                f"Data quality summary rows: {counts['data_quality_summary_rows']}\n"
                f"Invalid data quality rates: {counts['invalid_data_quality_rates']}\n"
                f"Invalid ingestion rates: {counts['invalid_ingestion_rates']}\n"
                f"Total dbt test failures recorded: {counts['total_dbt_test_failures']}"
            ),
            title="Sprint 10 Check",
        )
    )


if __name__ == "__main__":
    main()