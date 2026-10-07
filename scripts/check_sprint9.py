"""
check_sprint9.py

Validates Sprint 9 dbt snapshot history.

This script checks:
1. The snapshot table exists and has rows.
2. There is exactly one current row per job.
3. Snapshot row count is at least the number of canonical jobs.
4. Snapshot validity intervals are valid.

It does not modify the database.
"""

from rich.console import Console
from rich.panel import Panel

from job_market.db import get_connection

console = Console()


def fetch_counts() -> dict[str, int]:
    """
    Fetch Sprint 9 validation counts.

    Returns:
        dict[str, int]: Validation metrics.
    """

    query = """
        SELECT
            (
                SELECT COUNT(*)
                FROM dev_intermediate.int_job_posting_deduped
            ) AS canonical_jobs,

            (
                SELECT COUNT(*)
                FROM dev_snapshots.job_postings_snapshot
            ) AS snapshot_rows,

            (
                SELECT COUNT(*)
                FROM dev_snapshots.job_postings_snapshot
                WHERE dbt_valid_to IS NULL
            ) AS current_snapshot_rows,

            (
                SELECT COUNT(*)
                FROM (
                    SELECT
                        job_id
                    FROM dev_snapshots.job_postings_snapshot
                    WHERE dbt_valid_to IS NULL
                    GROUP BY job_id
                    HAVING COUNT(*) <> 1
                ) invalid_current_rows
            ) AS invalid_current_job_count,

            (
                SELECT COUNT(*)
                FROM dev_snapshots.job_postings_snapshot
                WHERE dbt_valid_to IS NOT NULL
                  AND dbt_valid_to < dbt_valid_from
            ) AS invalid_validity_intervals,

            (
                SELECT COUNT(*)
                FROM dev_snapshots.job_postings_snapshot
                WHERE dbt_valid_to IS NOT NULL
            ) AS historical_closed_rows;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Sprint 9 validation query returned no rows.")

    return {
        "canonical_jobs": row[0],
        "snapshot_rows": row[1],
        "current_snapshot_rows": row[2],
        "invalid_current_job_count": row[3],
        "invalid_validity_intervals": row[4],
        "historical_closed_rows": row[5],
    }


def main() -> None:
    """
    Validate Sprint 9 snapshot output.
    """

    console.print("[bold cyan]Checking Sprint 9 snapshot history...[/bold cyan]")

    try:
        counts = fetch_counts()
    except Exception as exc:
        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 9 validation failed.[/bold red]\n\n"
                    "Could not query the snapshot table.\n"
                    "Run `make dbt-build` and `make dbt-snapshot` first.\n\n"
                    f"Error: {exc}"
                ),
                title="Sprint 9 Check",
            )
        )
        raise SystemExit(1) from exc

    failures = []

    if counts["canonical_jobs"] == 0:
        failures.append("No canonical jobs found.")

    if counts["snapshot_rows"] == 0:
        failures.append("Snapshot table has no rows.")

    if counts["snapshot_rows"] < counts["canonical_jobs"]:
        failures.append("Snapshot row count is less than canonical job count.")

    if counts["current_snapshot_rows"] != counts["canonical_jobs"]:
        failures.append("Current snapshot row count does not match canonical job count.")

    if counts["invalid_current_job_count"] > 0:
        failures.append("Some jobs do not have exactly one current snapshot row.")

    if counts["invalid_validity_intervals"] > 0:
        failures.append("Invalid snapshot validity intervals found.")

    if failures:
        failure_text = "\n".join(f"- {failure}" for failure in failures)

        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 9 validation failed.[/bold red]\n\n"
                    f"{failure_text}\n\n"
                    f"Counts:\n{counts}"
                ),
                title="Sprint 9 Check",
            )
        )

        raise SystemExit(1)

    console.print(
        Panel.fit(
            (
                "[bold green]Sprint 9 validation passed.[/bold green]\n\n"
                f"Canonical jobs: {counts['canonical_jobs']}\n"
                f"Snapshot rows: {counts['snapshot_rows']}\n"
                f"Current snapshot rows: {counts['current_snapshot_rows']}\n"
                f"Closed historical rows: {counts['historical_closed_rows']}\n"
                f"Invalid current job count: {counts['invalid_current_job_count']}\n"
                f"Invalid validity intervals: {counts['invalid_validity_intervals']}"
            ),
            title="Sprint 9 Check",
        )
    )


if __name__ == "__main__":
    main()
