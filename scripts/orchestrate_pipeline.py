"""
orchestrate_pipeline.py

Sprint 13 pipeline orchestrator.

This script runs the complete job market warehouse pipeline unattended.

Pipeline flow:
1. Create ops.pipeline_runs row
2. Run Adzuna ingestion
3. Validate latest ingestion batch
4. Run dbt source freshness
5. Run dbt build
6. Parse dbt test results
7. Run dbt snapshot
8. Rebuild operational health marts
9. Update ops.pipeline_runs with SUCCESS or FAILED

This is intentionally a simple Python orchestrator rather than Airflow.
"""

from __future__ import annotations

import json
import os
import subprocess
from dataclasses import dataclass
from uuid import UUID

from dotenv import dotenv_values
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from job_market.config import ENV_FILE, PROJECT_ROOT
from job_market.repository import (
    create_pipeline_run,
    get_ingestion_batch_summary,
    get_latest_ingestion_batch_after,
    mark_pipeline_run_failed,
    mark_pipeline_run_success,
)

console = Console()


@dataclass(frozen=True)
class CommandResult:
    """
    Result of one orchestrated command.
    """

    step_name: str
    command: list[str]
    return_code: int
    stdout: str
    stderr: str


@dataclass(frozen=True)
class DbtResultSummary:
    """
    Summary parsed from dbt target/run_results.json.
    """

    dbt_invocation_id: str | None
    tests_passed: int
    tests_failed: int
    tests_warned: int


def build_subprocess_env() -> dict[str, str]:
    """
    Build environment variables for subprocess commands.

    The Python process can read .env through project config, but subprocesses
    such as dbt also need those variables. This function explicitly loads .env
    and merges it into the subprocess environment.
    """

    env = os.environ.copy()

    if ENV_FILE.exists():
        env_values = dotenv_values(ENV_FILE)

        for key, value in env_values.items():
            if value is not None:
                env[key] = value

    return env


def get_env_value(name: str, default: str) -> str:
    """
    Read a setting from environment or .env.

    Args:
        name: Environment variable name.
        default: Default value.

    Returns:
        str: Setting value.
    """

    env = build_subprocess_env()
    return env.get(name, default)


def get_git_sha() -> str | None:
    """
    Return current short Git SHA if the project is inside a Git repository.
    """

    result = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
    )

    if result.returncode != 0:
        return None

    return result.stdout.strip()


def run_command(
    *,
    step_name: str,
    command: list[str],
    allow_failure: bool = False,
) -> CommandResult:
    """
    Run a subprocess command and optionally fail the orchestrator.

    Args:
        step_name: Human-readable pipeline step name.
        command: Command list.
        allow_failure: Whether non-zero exit codes are allowed.

    Returns:
        CommandResult: Captured command result.

    Raises:
        RuntimeError: If command fails and allow_failure is False.
    """

    console.print(f"\n[bold cyan]Step:[/bold cyan] {step_name}")
    console.print(f"[cyan]Command:[/cyan] {' '.join(command)}")

    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=build_subprocess_env(),
        text=True,
        capture_output=True,
    )

    if result.stdout:
        console.print(result.stdout)

    if result.stderr:
        console.print(result.stderr)

    command_result = CommandResult(
        step_name=step_name,
        command=command,
        return_code=result.returncode,
        stdout=result.stdout,
        stderr=result.stderr,
    )

    if result.returncode != 0 and not allow_failure:
        raise RuntimeError(
            f"{step_name} failed with exit code {result.returncode}: {' '.join(command)}"
        )

    return command_result


def parse_dbt_run_results() -> DbtResultSummary:
    """
    Parse dbt run_results.json after dbt build.

    Returns:
        DbtResultSummary: dbt invocation ID and test counts.
    """

    run_results_path = PROJECT_ROOT / "dbt_job_market" / "target" / "run_results.json"

    if not run_results_path.exists():
        return DbtResultSummary(
            dbt_invocation_id=None,
            tests_passed=0,
            tests_failed=0,
            tests_warned=0,
        )

    payload = json.loads(run_results_path.read_text(encoding="utf-8"))

    dbt_invocation_id = payload.get("metadata", {}).get("invocation_id")

    tests_passed = 0
    tests_failed = 0
    tests_warned = 0

    for result in payload.get("results", []):
        unique_id = result.get("unique_id", "")
        status = result.get("status")

        if not unique_id.startswith("test."):
            continue

        if status == "pass":
            tests_passed += 1

        elif status == "warn":
            tests_warned += 1

        elif status in {"fail", "error"}:
            tests_failed += 1

    return DbtResultSummary(
        dbt_invocation_id=dbt_invocation_id,
        tests_passed=tests_passed,
        tests_failed=tests_failed,
        tests_warned=tests_warned,
    )


def validate_ingestion_batch(batch_id: UUID | None) -> dict:
    """
    Validate the latest ingestion batch before continuing to dbt.

    Args:
        batch_id: Latest ingestion batch ID.

    Returns:
        dict: Batch summary.

    Raises:
        RuntimeError: If batch does not exist or did not succeed.
    """

    if batch_id is None:
        raise RuntimeError("No ingestion batch was created by the ingestion step.")

    batch_summary = get_ingestion_batch_summary(batch_id)

    if batch_summary is None:
        raise RuntimeError(f"Ingestion batch was not found: {batch_id}")

    if batch_summary["status"] != "SUCCESS":
        raise RuntimeError(
            "Ingestion batch did not succeed. "
            f"Batch ID: {batch_id}, "
            f"Status: {batch_summary['status']}, "
            f"Error: {batch_summary['error_message']}"
        )

    if batch_summary["records_loaded"] <= 0:
        raise RuntimeError(
            f"Ingestion batch succeeded but loaded zero records. Batch ID: {batch_id}"
        )

    return batch_summary


def run_dbt_source_freshness(dbt_target: str) -> None:
    """
    Run dbt source freshness.
    """

    run_command(
        step_name="dbt source freshness",
        command=[
            "dbt",
            "source",
            "freshness",
            "--project-dir",
            "dbt_job_market",
            "--profiles-dir",
            "dbt_job_market",
            "--target",
            dbt_target,
        ],
    )


def run_dbt_build(dbt_target: str) -> DbtResultSummary:
    """
    Run dbt build and return parsed test results.
    """

    run_command(
        step_name="dbt build",
        command=[
            "dbt",
            "build",
            "--project-dir",
            "dbt_job_market",
            "--profiles-dir",
            "dbt_job_market",
            "--target",
            dbt_target,
        ],
    )

    return parse_dbt_run_results()


def run_dbt_snapshot(dbt_target: str) -> None:
    """
    Run dbt snapshots.
    """

    run_command(
        step_name="dbt snapshot",
        command=[
            "dbt",
            "snapshot",
            "--project-dir",
            "dbt_job_market",
            "--profiles-dir",
            "dbt_job_market",
            "--target",
            dbt_target,
        ],
    )


def rebuild_operational_marts(dbt_target: str) -> None:
    """
    Rebuild operational marts after ops.pipeline_runs has been updated.

    This lets mart_pipeline_health reflect the final pipeline status.
    """

    run_command(
        step_name="rebuild operational marts",
        command=[
            "dbt",
            "build",
            "--project-dir",
            "dbt_job_market",
            "--profiles-dir",
            "dbt_job_market",
            "--target",
            dbt_target,
            "--select",
            "mart_pipeline_health",
            "mart_api_request_summary",
            "mart_ingestion_batch_summary",
            "mart_data_quality_summary",
        ],
    )


def render_success_summary(
    *,
    pipeline_run_id: UUID,
    ingestion_batch_id: UUID | None,
    batch_summary: dict,
    dbt_summary: DbtResultSummary,
    dbt_target: str,
) -> None:
    """
    Render final success summary.
    """

    table = Table(title="Pipeline Success Summary")

    table.add_column("Field")
    table.add_column("Value")

    table.add_row("pipeline_run_id", str(pipeline_run_id))
    table.add_row("dbt_target", dbt_target)
    table.add_row("ingestion_batch_id", str(ingestion_batch_id))
    table.add_row("records_loaded", str(batch_summary["records_loaded"]))
    table.add_row("records_received", str(batch_summary["records_received"]))
    table.add_row("records_quarantined", str(batch_summary["records_quarantined"]))
    table.add_row("api_requests_made", str(batch_summary["api_requests_made"]))
    table.add_row("tests_passed", str(dbt_summary.tests_passed))
    table.add_row("tests_failed", str(dbt_summary.tests_failed))
    table.add_row("tests_warned", str(dbt_summary.tests_warned))
    table.add_row("dbt_invocation_id", str(dbt_summary.dbt_invocation_id))

    console.print(table)


def main() -> None:
    """
    Run the full orchestrated pipeline.
    """

    pipeline_name = get_env_value(
        "ORCHESTRATOR_PIPELINE_NAME",
        "job_market_warehouse_pipeline",
    )

    trigger_type = get_env_value("ORCHESTRATOR_TRIGGER_TYPE", "MANUAL").upper()
    dbt_target = get_env_value("ORCHESTRATOR_DBT_TARGET", "dev")

    if trigger_type not in {"MANUAL", "SCHEDULED", "CI"}:
        raise ValueError("ORCHESTRATOR_TRIGGER_TYPE must be one of MANUAL, SCHEDULED, CI.")

    git_sha = get_git_sha()

    pipeline_run_id, pipeline_started_at = create_pipeline_run(
        pipeline_name=pipeline_name,
        trigger_type=trigger_type,
        git_sha=git_sha,
    )

    console.print(
        Panel.fit(
            (
                "[bold cyan]Started orchestrated pipeline[/bold cyan]\n\n"
                f"Pipeline run ID: {pipeline_run_id}\n"
                f"Pipeline name: {pipeline_name}\n"
                f"Trigger type: {trigger_type}\n"
                f"dbt target: {dbt_target}\n"
                f"Git SHA: {git_sha}"
            ),
            title="Sprint 13",
        )
    )

    ingestion_batch_id: UUID | None = None
    dbt_summary = DbtResultSummary(
        dbt_invocation_id=None,
        tests_passed=0,
        tests_failed=0,
        tests_warned=0,
    )

    try:
        run_command(
            step_name="Adzuna ingestion",
            command=["python", "scripts/run_adzuna_ingestion.py"],
        )

        ingestion_batch_id = get_latest_ingestion_batch_after(pipeline_started_at)

        batch_summary = validate_ingestion_batch(ingestion_batch_id)

        run_dbt_source_freshness(dbt_target)

        dbt_summary = run_dbt_build(dbt_target)

        if dbt_summary.tests_failed > 0:
            raise RuntimeError(f"dbt build completed but {dbt_summary.tests_failed} tests failed.")

        run_dbt_snapshot(dbt_target)

        mark_pipeline_run_success(
            pipeline_run_id=pipeline_run_id,
            ingestion_batch_id=ingestion_batch_id,
            dbt_invocation_id=dbt_summary.dbt_invocation_id,
            tests_passed=dbt_summary.tests_passed,
            tests_failed=dbt_summary.tests_failed,
        )

        rebuild_operational_marts(dbt_target)

        render_success_summary(
            pipeline_run_id=pipeline_run_id,
            ingestion_batch_id=ingestion_batch_id,
            batch_summary=batch_summary,
            dbt_summary=dbt_summary,
            dbt_target=dbt_target,
        )

        console.print(
            Panel.fit(
                "[bold green]Pipeline completed successfully.[/bold green]",
                title="Sprint 13",
            )
        )

    except Exception as exc:
        dbt_summary = parse_dbt_run_results()

        mark_pipeline_run_failed(
            pipeline_run_id=pipeline_run_id,
            ingestion_batch_id=ingestion_batch_id,
            dbt_invocation_id=dbt_summary.dbt_invocation_id,
            dbt_status="FAILED",
            tests_passed=dbt_summary.tests_passed,
            tests_failed=dbt_summary.tests_failed,
            error_message=str(exc),
        )

        try:
            rebuild_operational_marts(dbt_target)
        except Exception as rebuild_exc:
            console.print(
                f"[yellow]Could not rebuild operational marts after failure: {rebuild_exc}[/yellow]"
            )

        console.print(
            Panel.fit(
                (
                    "[bold red]Pipeline failed.[/bold red]\n\n"
                    f"Pipeline run ID: {pipeline_run_id}\n"
                    f"Ingestion batch ID: {ingestion_batch_id}\n"
                    f"Error: {exc}"
                ),
                title="Sprint 13",
            )
        )

        raise


if __name__ == "__main__":
    main()
