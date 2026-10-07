"""
init_database.py

Initializes the PostgreSQL database for the Job Market Analytics Warehouse.

The script executes versioned SQL files from the project's sql/ directory
in filename order.

The SQL files are written to be idempotent where appropriate, so rerunning
this setup should not duplicate configuration records.
"""

from pathlib import Path

from rich.console import Console
from rich.panel import Panel

from job_market.db import execute_sql_file

console = Console()

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SQL_DIRECTORY = PROJECT_ROOT / "sql"


def get_sql_files() -> list[Path]:
    """
    Return project SQL setup files in deterministic execution order.

    Returns:
        list[Path]: Sorted SQL files from the sql directory.
    """

    return sorted(SQL_DIRECTORY.glob("[0-9][0-9][0-9]_*.sql"))


def main() -> None:
    """
    Execute all database foundation SQL files.
    """

    sql_files = get_sql_files()

    if not sql_files:
        console.print("[bold yellow]No database SQL files were found.[/bold yellow]")
        raise SystemExit(1)

    console.print("[bold cyan]Initializing project database...[/bold cyan]\n")

    for sql_file in sql_files:
        console.print(f"Running [bold]{sql_file.name}[/bold]")

        try:
            execute_sql_file(sql_file)
        except Exception as exc:
            console.print(
                Panel.fit(
                    (
                        f"[bold red]Database initialization failed[/bold red]\n\n"
                        f"File: {sql_file.name}\n"
                        f"Error: {exc}"
                    ),
                    title="Sprint 1",
                )
            )

            raise SystemExit(1) from exc

    console.print(
        Panel.fit(
            "[bold green]Database foundation initialized successfully.[/bold green]",
            title="Sprint 1",
        )
    )


if __name__ == "__main__":
    main()
