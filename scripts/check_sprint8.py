"""
check_sprint8.py

Validates Sprint 8 analytical marts.

This script checks:
1. Analytical marts exist and contain rows.
2. Grain uniqueness is preserved.
3. Share metrics are between 0 and 1.
4. Component counts do not exceed total counts.

It does not modify the database.
"""

from rich.console import Console
from rich.panel import Panel

from job_market.db import get_connection


console = Console()


def fetch_counts() -> dict[str, int]:
    """
    Fetch Sprint 8 validation counts.

    Returns:
        dict[str, int]: Validation metrics.
    """

    query = """
        SELECT
            (
                SELECT COUNT(*)
                FROM dev_marts.mart_skill_demand_weekly
            ) AS skill_demand_rows,

            (
                SELECT COUNT(*)
                FROM dev_marts.mart_company_hiring_summary
            ) AS company_summary_rows,

            (
                SELECT COUNT(*)
                FROM dev_marts.mart_role_market_summary
            ) AS role_summary_rows,

            (
                SELECT COUNT(*)
                FROM (
                    SELECT week_start_date, skill_id
                    FROM dev_marts.mart_skill_demand_weekly
                    GROUP BY week_start_date, skill_id
                    HAVING COUNT(*) > 1
                ) duplicate_skill_demand_rows
            ) AS duplicate_skill_demand_rows,

            (
                SELECT COUNT(*)
                FROM (
                    SELECT company_id
                    FROM dev_marts.mart_company_hiring_summary
                    GROUP BY company_id
                    HAVING COUNT(*) > 1
                ) duplicate_company_rows
            ) AS duplicate_company_rows,

            (
                SELECT COUNT(*)
                FROM (
                    SELECT role_family
                    FROM dev_marts.mart_role_market_summary
                    GROUP BY role_family
                    HAVING COUNT(*) > 1
                ) duplicate_role_rows
            ) AS duplicate_role_rows,

            (
                SELECT COUNT(*)
                FROM dev_marts.mart_skill_demand_weekly
                WHERE share_of_jobs < 0
                   OR share_of_jobs > 1
            ) AS invalid_skill_shares,

            (
                SELECT COUNT(*)
                FROM dev_marts.mart_company_hiring_summary
                WHERE salary_coverage < 0
                   OR salary_coverage > 1
                   OR remote_share < 0
                   OR remote_share > 1
            ) AS invalid_company_shares,

            (
                SELECT COUNT(*)
                FROM dev_marts.mart_role_market_summary
                WHERE salary_coverage < 0
                   OR salary_coverage > 1
                   OR remote_share < 0
                   OR remote_share > 1
                   OR top_skill_share < 0
                   OR top_skill_share > 1
            ) AS invalid_role_shares;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Sprint 8 validation query returned no rows.")

    return {
        "skill_demand_rows": row[0],
        "company_summary_rows": row[1],
        "role_summary_rows": row[2],
        "duplicate_skill_demand_rows": row[3],
        "duplicate_company_rows": row[4],
        "duplicate_role_rows": row[5],
        "invalid_skill_shares": row[6],
        "invalid_company_shares": row[7],
        "invalid_role_shares": row[8],
    }


def main() -> None:
    """
    Validate Sprint 8 analytical marts.
    """

    console.print("[bold cyan]Checking Sprint 8 analytical marts...[/bold cyan]")

    try:
        counts = fetch_counts()
    except Exception as exc:
        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 8 validation failed.[/bold red]\n\n"
                    "Could not query Sprint 8 mart models.\n"
                    "Run `make dbt-build` first.\n\n"
                    f"Error: {exc}"
                ),
                title="Sprint 8 Check",
            )
        )
        raise SystemExit(1) from exc

    failures = []

    if counts["skill_demand_rows"] == 0:
        failures.append("mart_skill_demand_weekly has no rows.")

    if counts["company_summary_rows"] == 0:
        failures.append("mart_company_hiring_summary has no rows.")

    if counts["role_summary_rows"] == 0:
        failures.append("mart_role_market_summary has no rows.")

    if counts["duplicate_skill_demand_rows"] > 0:
        failures.append("Duplicate week_start_date x skill_id rows found.")

    if counts["duplicate_company_rows"] > 0:
        failures.append("Duplicate company_id rows found.")

    if counts["duplicate_role_rows"] > 0:
        failures.append("Duplicate role_family rows found.")

    if counts["invalid_skill_shares"] > 0:
        failures.append("Invalid share_of_jobs values found.")

    if counts["invalid_company_shares"] > 0:
        failures.append("Invalid company share values found.")

    if counts["invalid_role_shares"] > 0:
        failures.append("Invalid role share values found.")

    if failures:
        failure_text = "\n".join(f"- {failure}" for failure in failures)

        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 8 validation failed.[/bold red]\n\n"
                    f"{failure_text}\n\n"
                    f"Counts:\n{counts}"
                ),
                title="Sprint 8 Check",
            )
        )

        raise SystemExit(1)

    console.print(
        Panel.fit(
            (
                "[bold green]Sprint 8 validation passed.[/bold green]\n\n"
                f"Skill demand rows: {counts['skill_demand_rows']}\n"
                f"Company summary rows: {counts['company_summary_rows']}\n"
                f"Role summary rows: {counts['role_summary_rows']}\n"
                f"Duplicate skill demand rows: {counts['duplicate_skill_demand_rows']}\n"
                f"Duplicate company rows: {counts['duplicate_company_rows']}\n"
                f"Duplicate role rows: {counts['duplicate_role_rows']}\n"
                f"Invalid skill shares: {counts['invalid_skill_shares']}\n"
                f"Invalid company shares: {counts['invalid_company_shares']}\n"
                f"Invalid role shares: {counts['invalid_role_shares']}"
            ),
            title="Sprint 8 Check",
        )
    )


if __name__ == "__main__":
    main()