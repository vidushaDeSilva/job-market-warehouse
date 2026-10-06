"""
apply_retention_policies.py

Applies Sprint 11 retention policies.

Default mode is dry-run. No data is deleted unless --execute is passed.

The script reads raw.retention_policies, but it only executes known whitelisted
policy names. This prevents arbitrary SQL stored in the database from being
executed accidentally.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterable

from psycopg import sql
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from job_market.config import PROJECT_ROOT
from job_market.db import get_connection


console = Console()


@dataclass(frozen=True)
class RetentionPolicy:
    """
    One retention policy loaded from raw.retention_policies.
    """

    policy_name: str
    data_area: str
    target_type: str
    target_identifier: str
    retention_days: int
    retention_action: str
    is_enabled: bool
    protect_current_records: bool


@dataclass(frozen=True)
class RetentionResult:
    """
    Result of applying or dry-running one retention policy.
    """

    policy_name: str
    target_identifier: str
    eligible_count: int
    deleted_count: int
    mode: str
    status: str
    message: str


def load_enabled_policies(selected_policy_names: set[str] | None) -> list[RetentionPolicy]:
    """
    Load enabled retention policies from the database.

    Args:
        selected_policy_names: Optional selected policies.

    Returns:
        list[RetentionPolicy]: Enabled policies.
    """

    query = """
        SELECT
            policy_name,
            data_area,
            target_type,
            target_identifier,
            retention_days,
            retention_action,
            is_enabled,
            protect_current_records
        FROM raw.retention_policies
        WHERE is_enabled = TRUE
        ORDER BY policy_name;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            rows = cursor.fetchall()

    policies = [
        RetentionPolicy(
            policy_name=row[0],
            data_area=row[1],
            target_type=row[2],
            target_identifier=row[3],
            retention_days=row[4],
            retention_action=row[5],
            is_enabled=row[6],
            protect_current_records=row[7],
        )
        for row in rows
    ]

    if selected_policy_names is None:
        return policies

    return [
        policy
        for policy in policies
        if policy.policy_name in selected_policy_names
    ]


def table_exists(schema_name: str, table_name: str) -> bool:
    """
    Check whether a database table exists.

    Args:
        schema_name: PostgreSQL schema name.
        table_name: PostgreSQL table name.

    Returns:
        bool: True if table exists.
    """

    query = """
        SELECT EXISTS (
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = %(schema_name)s
              AND table_name = %(table_name)s
        );
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                query,
                {
                    "schema_name": schema_name,
                    "table_name": table_name,
                },
            )
            row = cursor.fetchone()

    return bool(row and row[0])


def count_then_delete(
    *,
    count_query: sql.SQL,
    delete_query: sql.SQL,
    params: dict,
    execute: bool,
) -> tuple[int, int]:
    """
    Count eligible rows and optionally delete them.

    Args:
        count_query: SQL query that returns eligible row count.
        delete_query: SQL delete query.
        params: Query parameters.
        execute: Whether to actually delete.

    Returns:
        tuple[int, int]: eligible_count, deleted_count.
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(count_query, params)
            row = cursor.fetchone()
            eligible_count = int(row[0]) if row else 0

            deleted_count = 0

            if execute and eligible_count > 0:
                cursor.execute(delete_query, params)
                deleted_count = cursor.rowcount

        if execute:
            connection.commit()
        else:
            connection.rollback()

    return eligible_count, deleted_count


def apply_raw_successful_observations(
    policy: RetentionPolicy,
    *,
    execute: bool,
) -> RetentionResult:
    """
    Delete old successful raw job observations.
    """

    count_query = sql.SQL(
        """
        SELECT COUNT(*)
        FROM raw.source_adzuna_jobs j
        INNER JOIN raw.ingestion_batches b
            ON j.batch_id = b.batch_id
        WHERE b.status = 'SUCCESS'
          AND j.collected_at < NOW() - (%(retention_days)s * INTERVAL '1 day');
        """
    )

    delete_query = sql.SQL(
        """
        DELETE FROM raw.source_adzuna_jobs j
        USING raw.ingestion_batches b
        WHERE j.batch_id = b.batch_id
          AND b.status = 'SUCCESS'
          AND j.collected_at < NOW() - (%(retention_days)s * INTERVAL '1 day');
        """
    )

    eligible_count, deleted_count = count_then_delete(
        count_query=count_query,
        delete_query=delete_query,
        params={"retention_days": policy.retention_days},
        execute=execute,
    )

    return RetentionResult(
        policy_name=policy.policy_name,
        target_identifier=policy.target_identifier,
        eligible_count=eligible_count,
        deleted_count=deleted_count,
        mode="execute" if execute else "dry-run",
        status="ok",
        message="Old successful raw observations processed.",
    )


def apply_raw_api_responses(
    policy: RetentionPolicy,
    *,
    execute: bool,
) -> RetentionResult:
    """
    Delete old API response rows.

    Deleting API responses can cascade to job observations through foreign keys.
    Therefore this policy should not have shorter retention than raw observations.
    """

    count_query = sql.SQL(
        """
        SELECT COUNT(*)
        FROM raw.adzuna_api_responses
        WHERE response_received_at < NOW() - (%(retention_days)s * INTERVAL '1 day');
        """
    )

    delete_query = sql.SQL(
        """
        DELETE FROM raw.adzuna_api_responses
        WHERE response_received_at < NOW() - (%(retention_days)s * INTERVAL '1 day');
        """
    )

    eligible_count, deleted_count = count_then_delete(
        count_query=count_query,
        delete_query=delete_query,
        params={"retention_days": policy.retention_days},
        execute=execute,
    )

    return RetentionResult(
        policy_name=policy.policy_name,
        target_identifier=policy.target_identifier,
        eligible_count=eligible_count,
        deleted_count=deleted_count,
        mode="execute" if execute else "dry-run",
        status="ok",
        message="Old API responses processed.",
    )


def apply_quarantined_records(
    policy: RetentionPolicy,
    *,
    execute: bool,
) -> RetentionResult:
    """
    Delete old quarantined records.
    """

    count_query = sql.SQL(
        """
        SELECT COUNT(*)
        FROM raw.quarantined_records
        WHERE created_at < NOW() - (%(retention_days)s * INTERVAL '1 day');
        """
    )

    delete_query = sql.SQL(
        """
        DELETE FROM raw.quarantined_records
        WHERE created_at < NOW() - (%(retention_days)s * INTERVAL '1 day');
        """
    )

    eligible_count, deleted_count = count_then_delete(
        count_query=count_query,
        delete_query=delete_query,
        params={"retention_days": policy.retention_days},
        execute=execute,
    )

    return RetentionResult(
        policy_name=policy.policy_name,
        target_identifier=policy.target_identifier,
        eligible_count=eligible_count,
        deleted_count=deleted_count,
        mode="execute" if execute else "dry-run",
        status="ok",
        message="Old quarantined records processed.",
    )


def apply_ingestion_metadata(
    policy: RetentionPolicy,
    *,
    execute: bool,
) -> RetentionResult:
    """
    Delete old ingestion batch metadata.

    This may cascade to remaining child rows through foreign keys.
    """

    count_query = sql.SQL(
        """
        SELECT COUNT(*)
        FROM raw.ingestion_batches
        WHERE started_at < NOW() - (%(retention_days)s * INTERVAL '1 day');
        """
    )

    delete_query = sql.SQL(
        """
        DELETE FROM raw.ingestion_batches
        WHERE started_at < NOW() - (%(retention_days)s * INTERVAL '1 day');
        """
    )

    eligible_count, deleted_count = count_then_delete(
        count_query=count_query,
        delete_query=delete_query,
        params={"retention_days": policy.retention_days},
        execute=execute,
    )

    return RetentionResult(
        policy_name=policy.policy_name,
        target_identifier=policy.target_identifier,
        eligible_count=eligible_count,
        deleted_count=deleted_count,
        mode="execute" if execute else "dry-run",
        status="ok",
        message="Old ingestion metadata processed.",
    )


def apply_pipeline_metadata(
    policy: RetentionPolicy,
    *,
    execute: bool,
) -> RetentionResult:
    """
    Delete old pipeline run metadata.
    """

    count_query = sql.SQL(
        """
        SELECT COUNT(*)
        FROM ops.pipeline_runs
        WHERE started_at < NOW() - (%(retention_days)s * INTERVAL '1 day');
        """
    )

    delete_query = sql.SQL(
        """
        DELETE FROM ops.pipeline_runs
        WHERE started_at < NOW() - (%(retention_days)s * INTERVAL '1 day');
        """
    )

    eligible_count, deleted_count = count_then_delete(
        count_query=count_query,
        delete_query=delete_query,
        params={"retention_days": policy.retention_days},
        execute=execute,
    )

    return RetentionResult(
        policy_name=policy.policy_name,
        target_identifier=policy.target_identifier,
        eligible_count=eligible_count,
        deleted_count=deleted_count,
        mode="execute" if execute else "dry-run",
        status="ok",
        message="Old pipeline metadata processed.",
    )


def apply_snapshot_history(
    policy: RetentionPolicy,
    *,
    execute: bool,
) -> RetentionResult:
    """
    Delete old closed snapshot history rows.

    Current snapshot rows are protected by:
        dbt_valid_to IS NOT NULL
    """

    import os

    dbt_schema = os.getenv("DBT_SCHEMA", "dev")
    snapshot_schema = f"{dbt_schema}_snapshots"
    snapshot_table = "job_postings_snapshot"

    if not table_exists(snapshot_schema, snapshot_table):
        return RetentionResult(
            policy_name=policy.policy_name,
            target_identifier=f"{snapshot_schema}.{snapshot_table}",
            eligible_count=0,
            deleted_count=0,
            mode="execute" if execute else "dry-run",
            status="skipped",
            message="Snapshot table does not exist yet.",
        )

    count_query = sql.SQL(
        """
        SELECT COUNT(*)
        FROM {snapshot_table}
        WHERE dbt_valid_to IS NOT NULL
          AND dbt_valid_to < NOW() - (%(retention_days)s * INTERVAL '1 day');
        """
    ).format(
        snapshot_table=sql.Identifier(snapshot_schema, snapshot_table)
    )

    delete_query = sql.SQL(
        """
        DELETE FROM {snapshot_table}
        WHERE dbt_valid_to IS NOT NULL
          AND dbt_valid_to < NOW() - (%(retention_days)s * INTERVAL '1 day');
        """
    ).format(
        snapshot_table=sql.Identifier(snapshot_schema, snapshot_table)
    )

    eligible_count, deleted_count = count_then_delete(
        count_query=count_query,
        delete_query=delete_query,
        params={"retention_days": policy.retention_days},
        execute=execute,
    )

    return RetentionResult(
        policy_name=policy.policy_name,
        target_identifier=f"{snapshot_schema}.{snapshot_table}",
        eligible_count=eligible_count,
        deleted_count=deleted_count,
        mode="execute" if execute else "dry-run",
        status="ok",
        message="Old closed snapshot rows processed. Current rows were protected.",
    )


def apply_local_dbt_logs(
    policy: RetentionPolicy,
    *,
    execute: bool,
) -> RetentionResult:
    """
    Delete local dbt log files older than the retention window.
    """

    logs_path = PROJECT_ROOT / policy.target_identifier

    if not logs_path.exists():
        return RetentionResult(
            policy_name=policy.policy_name,
            target_identifier=str(logs_path),
            eligible_count=0,
            deleted_count=0,
            mode="execute" if execute else "dry-run",
            status="skipped",
            message="Log directory does not exist.",
        )

    cutoff_timestamp = datetime.now(timezone.utc).timestamp() - (
        policy.retention_days * 24 * 60 * 60
    )

    eligible_files: list[Path] = []

    for path in logs_path.rglob("*"):
        if not path.is_file():
            continue

        if path.stat().st_mtime < cutoff_timestamp:
            eligible_files.append(path)

    deleted_count = 0

    if execute:
        for path in eligible_files:
            path.unlink()
            deleted_count += 1

    return RetentionResult(
        policy_name=policy.policy_name,
        target_identifier=str(logs_path),
        eligible_count=len(eligible_files),
        deleted_count=deleted_count,
        mode="execute" if execute else "dry-run",
        status="ok",
        message="Old local dbt log files processed.",
    )


POLICY_HANDLERS: dict[str, Callable[[RetentionPolicy], RetentionResult]] = {}


def apply_policy(policy: RetentionPolicy, *, execute: bool) -> RetentionResult:
    """
    Apply one whitelisted policy.

    Args:
        policy: Retention policy.
        execute: Whether to delete data.

    Returns:
        RetentionResult: Policy result.
    """

    handlers: dict[str, Callable[[RetentionPolicy, bool], RetentionResult]] = {
        "raw_successful_observations": lambda p, e: apply_raw_successful_observations(p, execute=e),
        "raw_api_responses": lambda p, e: apply_raw_api_responses(p, execute=e),
        "quarantined_records": lambda p, e: apply_quarantined_records(p, execute=e),
        "ingestion_metadata": lambda p, e: apply_ingestion_metadata(p, execute=e),
        "pipeline_metadata": lambda p, e: apply_pipeline_metadata(p, execute=e),
        "snapshot_history": lambda p, e: apply_snapshot_history(p, execute=e),
        "local_dbt_logs": lambda p, e: apply_local_dbt_logs(p, execute=e),
    }

    handler = handlers.get(policy.policy_name)

    if handler is None:
        return RetentionResult(
            policy_name=policy.policy_name,
            target_identifier=policy.target_identifier,
            eligible_count=0,
            deleted_count=0,
            mode="execute" if execute else "dry-run",
            status="skipped",
            message="No whitelisted cleanup handler exists for this policy.",
        )

    return handler(policy, execute)


def render_results(results: Iterable[RetentionResult]) -> None:
    """
    Display retention results.
    """

    table = Table(title="Retention Policy Results")

    table.add_column("Policy")
    table.add_column("Target")
    table.add_column("Eligible", justify="right")
    table.add_column("Deleted", justify="right")
    table.add_column("Mode")
    table.add_column("Status")
    table.add_column("Message")

    for result in results:
        table.add_row(
            result.policy_name,
            result.target_identifier,
            str(result.eligible_count),
            str(result.deleted_count),
            result.mode,
            result.status,
            result.message,
        )

    console.print(table)


def main() -> None:
    """
    Run retention cleanup in dry-run or execute mode.
    """

    parser = argparse.ArgumentParser(description="Apply retention policies.")

    parser.add_argument(
        "--execute",
        action="store_true",
        help="Actually delete eligible data. Without this flag, only dry-run counts are shown.",
    )

    parser.add_argument(
        "--policy",
        action="append",
        help="Optional policy name to run. Can be passed multiple times.",
    )

    args = parser.parse_args()

    execute = bool(args.execute)
    selected_policy_names = set(args.policy) if args.policy else None

    if execute:
        console.print(
            Panel.fit(
                "[bold red]EXECUTE mode enabled. Eligible data will be deleted.[/bold red]",
                title="Retention",
            )
        )
    else:
        console.print(
            Panel.fit(
                "[bold yellow]Dry-run mode. No data will be deleted.[/bold yellow]",
                title="Retention",
            )
        )

    policies = load_enabled_policies(selected_policy_names)

    if not policies:
        console.print("[red]No enabled retention policies found.[/red]")
        raise SystemExit(1)

    results = [
        apply_policy(policy, execute=execute)
        for policy in policies
    ]

    render_results(results)


if __name__ == "__main__":
    main()