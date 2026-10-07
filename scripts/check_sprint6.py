"""
check_sprint6.py

Validates Sprint 6 business transformation models.

This script checks:
1. Salary normalization has one row per canonical job.
2. Role classification has one row per canonical job.
3. Skill matches have no duplicate job x skill rows.
4. At least one skill match exists.

It does not modify the database.
"""

from rich.console import Console
from rich.panel import Panel

from job_market.db import get_connection

console = Console()


def fetch_counts() -> dict[str, int]:
    """
    Fetch Sprint 6 validation counts from PostgreSQL.

    Returns:
        dict[str, int]: Validation counts.
    """

    query = """
        SELECT
            (
                SELECT COUNT(*)
                FROM dev_intermediate.int_job_posting_deduped
            ) AS canonical_jobs,

            (
                SELECT COUNT(*)
                FROM dev_intermediate.int_salary_normalized
            ) AS salary_rows,

            (
                SELECT COUNT(*)
                FROM dev_intermediate.int_role_classification
            ) AS role_rows,

            (
                SELECT COUNT(*)
                FROM dev_intermediate.int_job_skill_matches
            ) AS skill_match_rows,

            (
                SELECT COUNT(*)
                FROM (
                    SELECT
                        job_id,
                        skill_name
                    FROM dev_intermediate.int_job_skill_matches
                    GROUP BY
                        job_id,
                        skill_name
                    HAVING COUNT(*) > 1
                ) duplicate_skill_matches
            ) AS duplicate_skill_match_count,

            (
                SELECT COUNT(*)
                FROM dev_intermediate.int_role_classification
                WHERE role_family = 'unknown'
            ) AS unknown_role_count;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Sprint 6 validation query returned no rows.")

    return {
        "canonical_jobs": row[0],
        "salary_rows": row[1],
        "role_rows": row[2],
        "skill_match_rows": row[3],
        "duplicate_skill_match_count": row[4],
        "unknown_role_count": row[5],
    }


def main() -> None:
    """
    Validate Sprint 6 business transformation outputs.
    """

    console.print("[bold cyan]Checking Sprint 6 business transformations...[/bold cyan]")

    try:
        counts = fetch_counts()
    except Exception as exc:
        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 6 validation failed.[/bold red]\n\n"
                    "Could not query Sprint 6 dbt models.\n"
                    "Run `make dbt-build` first.\n\n"
                    f"Error: {exc}"
                ),
                title="Sprint 6 Check",
            )
        )
        raise SystemExit(1) from exc

    failures = []

    if counts["canonical_jobs"] == 0:
        failures.append("No canonical jobs found.")

    if counts["salary_rows"] != counts["canonical_jobs"]:
        failures.append("Salary model does not have one row per canonical job.")

    if counts["role_rows"] != counts["canonical_jobs"]:
        failures.append("Role classification model does not have one row per canonical job.")

    if counts["duplicate_skill_match_count"] > 0:
        failures.append("Duplicate job_id x skill_name rows found in skill matches.")

    if counts["skill_match_rows"] == 0:
        failures.append("No skill matches found. Check skill dictionary or job descriptions.")

    if failures:
        failure_text = "\n".join(f"- {failure}" for failure in failures)

        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 6 validation failed.[/bold red]\n\n"
                    f"{failure_text}\n\n"
                    f"Canonical jobs: {counts['canonical_jobs']}\n"
                    f"Salary rows: {counts['salary_rows']}\n"
                    f"Role rows: {counts['role_rows']}\n"
                    f"Skill matches: {counts['skill_match_rows']}\n"
                    f"Duplicate skill matches: {counts['duplicate_skill_match_count']}\n"
                    f"Unknown role rows: {counts['unknown_role_count']}"
                ),
                title="Sprint 6 Check",
            )
        )

        raise SystemExit(1)

    console.print(
        Panel.fit(
            (
                "[bold green]Sprint 6 validation passed.[/bold green]\n\n"
                f"Canonical jobs: {counts['canonical_jobs']}\n"
                f"Salary rows: {counts['salary_rows']}\n"
                f"Role rows: {counts['role_rows']}\n"
                f"Skill matches: {counts['skill_match_rows']}\n"
                f"Duplicate skill matches: {counts['duplicate_skill_match_count']}\n"
                f"Unknown role rows: {counts['unknown_role_count']}"
            ),
            title="Sprint 6 Check",
        )
    )


if __name__ == "__main__":
    main()
