"""
check_sprint11.py

Validates Sprint 11 retention, recovery and rollback setup.

This script checks:
1. raw.retention_policies exists.
2. Required policies are present.
3. Retention windows are reasonable.
4. Snapshot retention is at least 1 year.
5. Cleanup script can be dry-run separately.

It does not delete data.
"""

from rich.console import Console
from rich.panel import Panel

from job_market.db import get_connection

console = Console()


REQUIRED_POLICIES = {
    "raw_successful_observations",
    "raw_api_responses",
    "quarantined_records",
    "ingestion_metadata",
    "pipeline_metadata",
    "snapshot_history",
    "local_dbt_logs",
}


def fetch_policy_summary() -> dict:
    """
    Fetch retention policy validation information.

    Returns:
        dict: Validation metrics.
    """

    query = """
        SELECT
            COUNT(*) AS policy_count,

            COUNT(*) FILTER (
                WHERE is_enabled = TRUE
            ) AS enabled_policy_count,

            COUNT(*) FILTER (
                WHERE retention_days <= 0
            ) AS invalid_retention_count,

            COUNT(*) FILTER (
                WHERE policy_name = 'snapshot_history'
                  AND retention_days >= 365
            ) AS valid_snapshot_policy_count
        FROM raw.retention_policies;
    """

    missing_query = """
        SELECT required_policy
        FROM UNNEST(%(required_policies)s::text[]) AS required_policy
        LEFT JOIN raw.retention_policies p
            ON p.policy_name = required_policy
        WHERE p.policy_name IS NULL;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()

            cursor.execute(
                missing_query,
                {"required_policies": list(REQUIRED_POLICIES)},
            )
            missing_rows = cursor.fetchall()

    if row is None:
        raise RuntimeError("Retention policy summary returned no row.")

    return {
        "policy_count": row[0],
        "enabled_policy_count": row[1],
        "invalid_retention_count": row[2],
        "valid_snapshot_policy_count": row[3],
        "missing_policies": [missing_row[0] for missing_row in missing_rows],
    }


def main() -> None:
    """
    Validate Sprint 11 setup.
    """

    console.print("[bold cyan]Checking Sprint 11 retention setup...[/bold cyan]")

    try:
        summary = fetch_policy_summary()
    except Exception as exc:
        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 11 validation failed.[/bold red]\n\n"
                    "Could not query raw.retention_policies.\n"
                    "Run `make db-init` first.\n\n"
                    f"Error: {exc}"
                ),
                title="Sprint 11 Check",
            )
        )
        raise SystemExit(1) from exc

    failures = []

    if summary["policy_count"] == 0:
        failures.append("No retention policies found.")

    if summary["enabled_policy_count"] == 0:
        failures.append("No enabled retention policies found.")

    if summary["invalid_retention_count"] > 0:
        failures.append("Some policies have invalid retention_days.")

    if summary["valid_snapshot_policy_count"] != 1:
        failures.append("Snapshot history retention must be at least 365 days.")

    if summary["missing_policies"]:
        failures.append("Missing required policies: " + ", ".join(summary["missing_policies"]))

    if failures:
        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 11 validation failed.[/bold red]\n\n"
                    + "\n".join(f"- {failure}" for failure in failures)
                    + f"\n\nSummary:\n{summary}"
                ),
                title="Sprint 11 Check",
            )
        )

        raise SystemExit(1)

    console.print(
        Panel.fit(
            (
                "[bold green]Sprint 11 validation passed.[/bold green]\n\n"
                f"Policies: {summary['policy_count']}\n"
                f"Enabled policies: {summary['enabled_policy_count']}\n"
                f"Invalid retention policies: {summary['invalid_retention_count']}\n"
                f"Snapshot retention valid: {summary['valid_snapshot_policy_count'] == 1}"
            ),
            title="Sprint 11 Check",
        )
    )


if __name__ == "__main__":
    main()
