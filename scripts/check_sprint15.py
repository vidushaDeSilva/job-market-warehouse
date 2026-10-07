"""
check_sprint15.py

Validates Sprint 15 serving layer.

Checks:
1. Dashboard marts exist.
2. Dashboard marts have expected rows.
3. Streamlit dependency is importable.
4. Dashboard source files exist.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from job_market.db import get_connection

console = Console()

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def fetch_summary() -> dict:
    """
    Fetch dashboard mart validation summary.
    """

    dbt_schema = os.getenv("DBT_SCHEMA", "dev")
    marts_schema = f"{dbt_schema}_marts"

    query = f"""
        SELECT
            (
                SELECT COUNT(*)
                FROM {marts_schema}.mart_job_market_overview
            ) AS overview_rows,

            (
                SELECT COUNT(*)
                FROM {marts_schema}.mart_salary_distribution
            ) AS salary_distribution_rows,

            (
                SELECT COUNT(*)
                FROM {marts_schema}.mart_pipeline_health
            ) AS pipeline_health_rows,

            (
                SELECT COUNT(*)
                FROM {marts_schema}.mart_data_quality_summary
            ) AS data_quality_rows;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Sprint 15 validation query returned no rows.")

    return {
        "overview_rows": row[0],
        "salary_distribution_rows": row[1],
        "pipeline_health_rows": row[2],
        "data_quality_rows": row[3],
    }


def main() -> None:
    """
    Validate Sprint 15.
    """

    console.print("[bold cyan]Checking Sprint 15 serving layer...[/bold cyan]")

    failures = []

    if importlib.util.find_spec("streamlit") is None:
        failures.append("Streamlit is not installed.")

    required_files = [
        PROJECT_ROOT / "dashboard" / "Home.py",
        PROJECT_ROOT / "dashboard" / "db.py",
        PROJECT_ROOT / "dashboard" / "components.py",
        PROJECT_ROOT / "dashboard" / "pages" / "1_Data_Health.py",
        PROJECT_ROOT / "dashboard" / "pages" / "2_Job_Explorer.py",
    ]

    for file_path in required_files:
        if not file_path.exists():
            failures.append(f"Missing dashboard file: {file_path}")

    try:
        summary = fetch_summary()
    except Exception as exc:
        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 15 validation failed.[/bold red]\n\n"
                    "Could not query dashboard marts.\n"
                    "Run `make dbt-build` first.\n\n"
                    f"Error: {exc}"
                ),
                title="Sprint 15 Check",
            )
        )
        raise SystemExit(1) from exc

    if summary["overview_rows"] != 1:
        failures.append("mart_job_market_overview should contain exactly one row.")

    if summary["pipeline_health_rows"] != 1:
        failures.append("mart_pipeline_health should contain exactly one row.")

    if summary["data_quality_rows"] != 1:
        failures.append("mart_data_quality_summary should contain exactly one row.")

    if failures:
        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 15 validation failed.[/bold red]\n\n"
                    + "\n".join(f"- {failure}" for failure in failures)
                    + f"\n\nSummary:\n{summary}"
                ),
                title="Sprint 15 Check",
            )
        )
        raise SystemExit(1)

    console.print(
        Panel.fit(
            (
                "[bold green]Sprint 15 validation passed.[/bold green]\n\n"
                f"Overview rows: {summary['overview_rows']}\n"
                f"Salary distribution rows: {summary['salary_distribution_rows']}\n"
                f"Pipeline health rows: {summary['pipeline_health_rows']}\n"
                f"Data quality rows: {summary['data_quality_rows']}"
            ),
            title="Sprint 15 Check",
        )
    )


if __name__ == "__main__":
    main()