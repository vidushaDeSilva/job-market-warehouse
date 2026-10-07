"""
db.py

Database utilities for the Job Market Analytics Warehouse.

This module centralizes PostgreSQL connection handling so that ingestion
scripts and database setup utilities do not create database connections
independently.

Sprint 1 also adds support for executing SQL migration/setup files.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

import psycopg
from psycopg import Connection

from job_market.config import get_settings


@contextmanager
def get_connection() -> Iterator[Connection]:
    """
    Open a PostgreSQL connection using DATABASE_URL.

    The connection is always closed after use.

    Yields:
        Connection: Active psycopg PostgreSQL connection.
    """

    settings = get_settings()

    connection = psycopg.connect(settings.database_url)

    try:
        yield connection
    finally:
        connection.close()


def check_database_connection() -> dict[str, str]:
    """
    Verify that PostgreSQL is reachable.

    Returns:
        dict[str, str]: Basic database metadata.

    Raises:
        RuntimeError: If PostgreSQL unexpectedly returns no result.
    """

    query = """
        SELECT
            current_database(),
            current_user,
            version();
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Database connection succeeded but PostgreSQL returned no metadata.")

    return {
        "database_name": row[0],
        "database_user": row[1],
        "postgres_version": row[2],
    }


def execute_sql_file(file_path: Path) -> None:
    """
    Execute all SQL commands contained in a file inside one transaction.

    If any SQL statement fails, the transaction is rolled back so that
    the database is not left half-configured.

    Args:
        file_path: Path to the SQL file that should be executed.

    Raises:
        FileNotFoundError: If the SQL file does not exist.
        psycopg.Error: If PostgreSQL rejects any SQL statement.
    """

    if not file_path.exists():
        raise FileNotFoundError(f"SQL file does not exist: {file_path}")

    sql_text = file_path.read_text(encoding="utf-8")

    with get_connection() as connection:
        try:
            with connection.cursor() as cursor:
                # No user-supplied values are interpolated here.
                # These are trusted migration files stored in the repository.
                cursor.execute(sql_text)

            connection.commit()

        except Exception:
            # An explicit rollback makes the transactional behavior easy
            # to understand and protects against partially applied scripts.
            connection.rollback()
            raise
