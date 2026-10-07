"""
drop_dbt_ci_schemas.py

Drops temporary dbt CI schemas after a GitHub Actions run.

This script is deliberately conservative:
- It only runs when DBT_SCHEMA starts with "ci_".
- It only drops dbt-generated schemas derived from DBT_SCHEMA.
- It refuses to touch dev, test, prod, raw, or ops schemas.
"""

from __future__ import annotations

import os

from psycopg import sql
from rich.console import Console
from rich.panel import Panel

from job_market.db import get_connection

console = Console()


PROTECTED_SCHEMA_PREFIXES = {
    "dev",
    "test",
    "prod",
    "raw",
    "ops",
}


def main() -> None:
    """
    Drop dbt schemas generated for a CI run.
    """

    base_schema = os.getenv("DBT_SCHEMA")

    if not base_schema:
        console.print("[yellow]DBT_SCHEMA is not set. Nothing to clean.[/yellow]")
        return

    if not base_schema.startswith("ci_"):
        raise RuntimeError(
            f"Refusing to drop schemas because DBT_SCHEMA is not a CI schema: {base_schema}"
        )

    if base_schema in PROTECTED_SCHEMA_PREFIXES:
        raise RuntimeError(f"Refusing to drop protected schema: {base_schema}")

    schemas_to_drop = [
        f"{base_schema}_staging",
        f"{base_schema}_intermediate",
        f"{base_schema}_marts",
        f"{base_schema}_snapshots",
        f"{base_schema}_reference",
    ]

    with get_connection() as connection:
        with connection.cursor() as cursor:
            for schema_name in schemas_to_drop:
                console.print(f"[cyan]Dropping schema if exists:[/cyan] {schema_name}")

                cursor.execute(
                    sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE;").format(sql.Identifier(schema_name))
                )

        connection.commit()

    console.print(
        Panel.fit(
            "[bold green]Temporary CI schemas cleaned successfully.[/bold green]",
            title="CI Cleanup",
        )
    )


if __name__ == "__main__":
    main()
