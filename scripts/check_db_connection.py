"""
check_db_connection.py

This script imports the project's database helper from the installed local
`job_market` package. The package is made available by running:

    pip install -e .

No tables are created or modified by this script. It only checks whether the
configured database connection works.
"""

from rich.console import Console
from rich.panel import Panel

from job_market.db import check_database_connection


console = Console()


def main() -> None:
    """
    Run the PostgreSQL connection check and print a readable result.
    """

    console.print("[bold cyan]Checking PostgreSQL connection...[/bold cyan]")

    try:
        result = check_database_connection()
    except Exception as exc:
        console.print(
            Panel.fit(
                f"[bold red]Database connection failed[/bold red]\n\n{exc}",
                title="Sprint 0 Check",
            )
        )
        raise SystemExit(1) from exc

    message = (
        "[bold green]Database connection successful[/bold green]\n\n"
        f"Database: {result['database_name']}\n"
        f"User: {result['database_user']}\n\n"
        f"PostgreSQL version:\n{result['postgres_version']}"
    )

    console.print(Panel.fit(message, title="Sprint 0 Check"))


if __name__ == "__main__":
    main()