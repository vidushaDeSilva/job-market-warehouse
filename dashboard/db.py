"""
db.py

Database access helpers for the Streamlit dashboard.

Dashboard rules:
- query only prepared marts
- prefer DASHBOARD_DATABASE_URL for a read-only dashboard user
- cache dashboard queries for 900 seconds
- never query raw or ops directly from the dashboard
"""

from __future__ import annotations

import os
import re

import pandas as pd
import psycopg
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

DEFAULT_CACHE_TTL_SECONDS = 900


def get_dashboard_database_url() -> str:
    """
    Return the dashboard database URL.

    DASHBOARD_DATABASE_URL should point to an analytics_readonly_role user.
    DATABASE_URL is allowed as a local development fallback.
    """

    database_url = os.getenv("DASHBOARD_DATABASE_URL") or os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError(
            "Missing database connection. Set DASHBOARD_DATABASE_URL or DATABASE_URL."
        )

    return database_url.strip()


def get_dashboard_schema() -> str:
    """
    Return the marts schema used by the dashboard.

    Default:
        dev_marts
    """

    schema = os.getenv("DASHBOARD_SCHEMA", "dev_marts").strip()

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", schema):
        raise RuntimeError(f"Invalid dashboard schema name: {schema}")

    if schema in {"raw", "ops"}:
        raise RuntimeError("Dashboard must not query raw or ops schemas directly.")

    if not schema.endswith("_marts"):
        raise RuntimeError(
            "Dashboard schema should be a prepared marts schema, for example dev_marts."
        )

    return schema


def get_cache_ttl_seconds() -> int:
    """
    Return dashboard cache TTL.
    """

    raw_value = os.getenv("DASHBOARD_CACHE_TTL_SECONDS", str(DEFAULT_CACHE_TTL_SECONDS))

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise RuntimeError("DASHBOARD_CACHE_TTL_SECONDS must be an integer.") from exc

    if value < 0:
        raise RuntimeError("DASHBOARD_CACHE_TTL_SECONDS must be non-negative.")

    return value


@st.cache_data(ttl=get_cache_ttl_seconds())
def run_query(query: str, params: tuple | None = None) -> pd.DataFrame:
    """
    Execute a SQL query and return a pandas DataFrame.
    """

    with psycopg.connect(get_dashboard_database_url()) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, params or ())
            rows = cursor.fetchall()
            columns = [description.name for description in cursor.description]

    return pd.DataFrame(rows, columns=columns)


def marts_table(table_name: str) -> str:
    """
    Return a schema-qualified marts table name.

    The table name is validated because it is interpolated into SQL.
    """

    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
        raise RuntimeError(f"Invalid marts table name: {table_name}")

    return f"{get_dashboard_schema()}.{table_name}"