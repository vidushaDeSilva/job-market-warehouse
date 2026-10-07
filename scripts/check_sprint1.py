"""
check_sprint1.py

Validates the database objects created during Sprint 1.

The script checks that the required schemas and metadata tables exist
and confirms that at least one Adzuna query configuration has been created.

It does not modify the database.
"""

from rich.console import Console
from rich.panel import Panel

from job_market.db import get_connection

console = Console()


EXPECTED_TABLES = {
    ("raw", "ingestion_batches"),
    ("raw", "adzuna_query_config"),
    ("ops", "pipeline_runs"),
    ("ops", "source_collection_state"),
}


def get_existing_tables() -> set[tuple[str, str]]:
    """
    Return raw and ops tables currently available in PostgreSQL.

    Returns:
        set[tuple[str, str]]: Pairs of schema and table names.
    """

    query = """
        SELECT
            table_schema,
            table_name
        FROM information_schema.tables
        WHERE table_schema IN ('raw', 'ops')
          AND table_type = 'BASE TABLE';
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    return {(row[0], row[1]) for row in rows}


def get_query_config_count() -> int:
    """
    Count configured Adzuna search definitions.

    Returns:
        int: Number of rows in raw.adzuna_query_config.
    """

    query = """
        SELECT COUNT(*)
        FROM raw.adzuna_query_config;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()

    if row is None:
        return 0

    return row[0]


def main() -> None:
    """
    Validate the Sprint 1 database foundation.
    """

    console.print("[bold cyan]Checking Sprint 1 database foundation...[/bold cyan]")

    existing_tables = get_existing_tables()

    missing_tables = EXPECTED_TABLES - existing_tables

    if missing_tables:
        formatted_missing = "\n".join(
            f"- {schema}.{table}" for schema, table in sorted(missing_tables)
        )

        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 1 validation failed.[/bold red]\n\n"
                    "Missing tables:\n"
                    f"{formatted_missing}"
                ),
                title="Sprint 1 Check",
            )
        )

        raise SystemExit(1)

    query_count = get_query_config_count()

    if query_count == 0:
        console.print(
            Panel.fit(
                "[bold red]No Adzuna query configurations were found.[/bold red]",
                title="Sprint 1 Check",
            )
        )

        raise SystemExit(1)

    table_names = "\n".join(f"✓ {schema}.{table}" for schema, table in sorted(EXPECTED_TABLES))

    console.print(
        Panel.fit(
            (
                "[bold green]Sprint 1 validation passed.[/bold green]\n\n"
                f"{table_names}\n\n"
                f"Adzuna query configurations: {query_count}"
            ),
            title="Sprint 1 Check",
        )
    )


if __name__ == "__main__":
    main()
