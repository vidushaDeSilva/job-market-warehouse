"""
run_observed_pipeline.py

Runs the end-to-end observed pipeline for Sprint 10.

This script records one row in ops.pipeline_runs for the full execution:

1. Create pipeline run
2. Run Adzuna ingestion
3. Run dbt build
4. Run dbt snapshot
5. Parse dbt test results
6. Update ops.pipeline_runs
7. Rebuild operational marts so they reflect the final pipeline status

This makes the pipeline observable rather than just executable.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
from uuid import UUID

from rich.console import Console
from rich.panel import Panel

from job_market.config import PROJECT_ROOT
from job_market.repository import (
    create_pipeline_run,
    get_latest_ingestion_batch_after,
    update_pipeline_run,
)


console = Console()

PIPELINE_NAME = "job_market_warehouse_pipeline"


def run_command(command: list[str], *, allow_failure: bool = False) -> subprocess.CompletedProcess:
    """
    Run a shell command from the project root.

    Args:
        command: Command and arguments.
        allow_failure: If False, raise when the command fails.

    Returns:
        subprocess.CompletedProcess: Completed subprocess result.
    """

    console.print(f"\n[cyan]Running:[/cyan] {' '.join(command)}")

    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        env=os.environ.copy(),
        text=True,
        capture_output=True,
    )

    if result.stdout:
        console.print(result.stdout)

    if result.stderr:
        console.print(result.stderr)

    if result.returncode != 0 and not allow_failure:
        raise RuntimeError(
            f"Command failed with exit code {result.returncode}: {' '.join(command)}"
        )

    return result


def get_git_sha() -> str | None:
    """
    Get current git commit SHA if the project is inside a git repository.

    Returns:
        str | None: Git SHA or None.
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


def parse_dbt_run_results() -> dict[str, int | str | None]:
    """
    Parse dbt target/run_results.json.

    Returns:
        dict: dbt invocation ID and test pass/fail counts.
    """

    run_results_path = PROJECT_ROOT / "dbt_job_market" / "target" / "run_results.json"

    if not run_results_path.exists():
        return {
            "dbt_invocation_id": None,
            "tests_passed": 0,
            "tests_failed": 0,
        }

    payload = json.loads(run_results_path.read_text(encoding="utf-8"))

    dbt_invocation_id = payload.get("metadata", {}).get("invocation_id")

    tests_passed = 0
    tests_failed = 0

    for result in payload.get("results", []):
        unique_id = result.get("unique_id", "")
        status = result.get("status")

        if not unique_id.startswith("test."):
            continue

        if status == "pass":
            tests_passed += 1

        elif status in {"fail", "error"}:
            tests_failed += 1

    return {
        "dbt_invocation_id": dbt_invocation_id,
        "tests_passed": tests_passed,
        "tests_failed": tests_failed,
    }


def rebuild_operational_marts() -> None:
    """
    Rebuild only Sprint 10 operational marts after ops.pipeline_runs is updated.

    This second small dbt build allows mart_pipeline_health to reflect the final
    pipeline status instead of the earlier STARTED status.
    """

    run_command(
        [
            "dbt",
            "build",
            "--project-dir",
            "dbt_job_market",
            "--profiles-dir",
            "dbt_job_market",
            "--select",
            "mart_pipeline_health",
            "mart_api_request_summary",
            "mart_ingestion_batch_summary",
            "mart_data_quality_summary",
        ]
    )


def main() -> None:
    """
    Run the observed pipeline and update ops.pipeline_runs.
    """

    git_sha = get_git_sha()

    pipeline_run_id, pipeline_started_at = create_pipeline_run(
        pipeline_name=PIPELINE_NAME,
        trigger_type="MANUAL",
        git_sha=git_sha,
    )

    console.print(
        Panel.fit(
            (
                "[bold cyan]Started observed pipeline run[/bold cyan]\n\n"
                f"Pipeline run ID: {pipeline_run_id}\n"
                f"Started at: {pipeline_started_at}\n"
                f"Git SHA: {git_sha}"
            ),
            title="Sprint 10",
        )
    )

    ingestion_batch_id: UUID | None = None
    dbt_invocation_id: str | None = None
    tests_passed = 0
    tests_failed = 0

    try:
        run_command(["python", "scripts/run_adzuna_ingestion.py"])

        ingestion_batch_id = get_latest_ingestion_batch_after(pipeline_started_at)

        run_command(
            [
                "dbt",
                "build",
                "--project-dir",
                "dbt_job_market",
                "--profiles-dir",
                "dbt_job_market",
            ]
        )

        dbt_results = parse_dbt_run_results()
        dbt_invocation_id = str(dbt_results["dbt_invocation_id"])
        tests_passed = int(dbt_results["tests_passed"])
        tests_failed = int(dbt_results["tests_failed"])

        run_command(
            [
                "dbt",
                "snapshot",
                "--project-dir",
                "dbt_job_market",
                "--profiles-dir",
                "dbt_job_market",
            ]
        )

        final_status = "SUCCESS" if tests_failed == 0 else "PARTIAL"

        update_pipeline_run(
            pipeline_run_id=pipeline_run_id,
            status=final_status,
            ingestion_batch_id=ingestion_batch_id,
            dbt_invocation_id=dbt_invocation_id,
            dbt_status="SUCCESS",
            tests_passed=tests_passed,
            tests_failed=tests_failed,
            error_message=None if tests_failed == 0 else "dbt build completed with test failures.",
        )

        rebuild_operational_marts()

        console.print(
            Panel.fit(
                (
                    "[bold green]Observed pipeline completed.[/bold green]\n\n"
                    f"Status: {final_status}\n"
                    f"Ingestion batch ID: {ingestion_batch_id}\n"
                    f"dbt invocation ID: {dbt_invocation_id}\n"
                    f"Tests passed: {tests_passed}\n"
                    f"Tests failed: {tests_failed}"
                ),
                title="Sprint 10",
            )
        )

    except Exception as exc:
        dbt_results = parse_dbt_run_results()
        dbt_invocation_id_value = dbt_results.get("dbt_invocation_id")

        update_pipeline_run(
            pipeline_run_id=pipeline_run_id,
            status="FAILED",
            ingestion_batch_id=ingestion_batch_id,
            dbt_invocation_id=str(dbt_invocation_id_value) if dbt_invocation_id_value else None,
            dbt_status="FAILED",
            tests_passed=int(dbt_results.get("tests_passed", 0)),
            tests_failed=int(dbt_results.get("tests_failed", 0)),
            error_message=str(exc),
        )

        console.print(
            Panel.fit(
                (
                    "[bold red]Observed pipeline failed.[/bold red]\n\n"
                    f"Pipeline run ID: {pipeline_run_id}\n"
                    f"Error: {exc}"
                ),
                title="Sprint 10",
            )
        )

        raise


if __name__ == "__main__":
    main()