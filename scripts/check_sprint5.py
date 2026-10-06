"""
check_sprint5.py

Validates Sprint 5 canonical job deduplication.

This script checks that:
1. The intermediate deduplicated model exists.
2. Canonical job count is not greater than staged observation count.
3. job_id is unique.
4. At least one canonical job exists.

It does not modify the database.
"""

from rich.console import Console
from rich.panel import Panel

from job_market.db import get_connection


console = Console()


def fetch_sprint5_counts() -> dict[str, int]:
    """
    Fetch observation and canonical job counts from PostgreSQL.

    Returns:
        dict[str, int]: Validation counts.
    """

    query = """
        SELECT
            (
                SELECT COUNT(*)
                FROM dev_staging.stg_adzuna_jobs
            ) AS staged_observation_count,

            (
                SELECT COUNT(*)
                FROM dev_intermediate.int_job_posting_deduped
            ) AS canonical_job_count,

            (
                SELECT COUNT(*)
                FROM (
                    SELECT job_id
                    FROM dev_intermediate.int_job_posting_deduped
                    GROUP BY job_id
                    HAVING COUNT(*) > 1
                ) duplicate_jobs
            ) AS duplicate_job_id_count,

            (
                SELECT COALESCE(MAX(observation_count), 0)
                FROM dev_intermediate.int_job_posting_deduped
            ) AS max_observation_count;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Sprint 5 validation query returned no result.")

    return {
        "staged_observation_count": row[0],
        "canonical_job_count": row[1],
        "duplicate_job_id_count": row[2],
        "max_observation_count": row[3],
    }


def main() -> None:
    """
    Validate canonical job deduplication.
    """

    console.print("[bold cyan]Checking Sprint 5 canonical job model...[/bold cyan]")

    try:
        counts = fetch_sprint5_counts()
    except Exception as exc:
        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 5 validation failed.[/bold red]\n\n"
                    "Could not query dbt staging/intermediate models.\n"
                    "Run `make dbt-build` first.\n\n"
                    f"Error: {exc}"
                ),
                title="Sprint 5 Check",
            )
        )
        raise SystemExit(1) from exc

    failures = []

    if counts["staged_observation_count"] == 0:
        failures.append("No staged Adzuna observations found.")

    if counts["canonical_job_count"] == 0:
        failures.append("No canonical jobs found.")

    if counts["canonical_job_count"] > counts["staged_observation_count"]:
        failures.append(
            "Canonical job count is greater than staged observation count."
        )

    if counts["duplicate_job_id_count"] > 0:
        failures.append("Duplicate job_id values found.")

    if failures:
        failure_text = "\n".join(f"- {failure}" for failure in failures)

        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 5 validation failed.[/bold red]\n\n"
                    f"{failure_text}\n\n"
                    f"Staged observations: {counts['staged_observation_count']}\n"
                    f"Canonical jobs: {counts['canonical_job_count']}\n"
                    f"Duplicate job IDs: {counts['duplicate_job_id_count']}\n"
                    f"Max observation count: {counts['max_observation_count']}"
                ),
                title="Sprint 5 Check",
            )
        )

        raise SystemExit(1)

    console.print(
        Panel.fit(
            (
                "[bold green]Sprint 5 validation passed.[/bold green]\n\n"
                f"Staged observations: {counts['staged_observation_count']}\n"
                f"Canonical jobs: {counts['canonical_job_count']}\n"
                f"Duplicate job IDs: {counts['duplicate_job_id_count']}\n"
                f"Max observation count for one canonical job: "
                f"{counts['max_observation_count']}"
            ),
            title="Sprint 5 Check",
        )
    )


if __name__ == "__main__":
    main()