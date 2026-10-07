"""
check_sprint7.py

Validates Sprint 7 dimensional warehouse models.

This script checks:
1. Dimension tables exist and have rows.
2. fact_job_postings has one row per canonical job.
3. fact_job_skill_mentions has one row per job x skill.
4. No duplicate primary grain values exist.
5. No orphan dimension references exist.

It does not modify the database.
"""

from rich.console import Console
from rich.panel import Panel

from job_market.db import get_connection

console = Console()


def fetch_counts() -> dict[str, int]:
    """
    Fetch Sprint 7 validation counts from PostgreSQL.

    Returns:
        dict[str, int]: Validation metrics.
    """

    query = """
        SELECT
            (
                SELECT COUNT(*)
                FROM dev_intermediate.int_job_posting_deduped
            ) AS canonical_jobs,

            (
                SELECT COUNT(*)
                FROM dev_intermediate.int_job_skill_matches
            ) AS intermediate_skill_matches,

            (
                SELECT COUNT(*)
                FROM dev_marts.dim_companies
            ) AS dim_companies,

            (
                SELECT COUNT(*)
                FROM dev_marts.dim_skills
            ) AS dim_skills,

            (
                SELECT COUNT(*)
                FROM dev_marts.dim_roles
            ) AS dim_roles,

            (
                SELECT COUNT(*)
                FROM dev_marts.fact_job_postings
            ) AS fact_job_postings,

            (
                SELECT COUNT(*)
                FROM dev_marts.fact_job_skill_mentions
            ) AS fact_job_skill_mentions,

            (
                SELECT COUNT(*)
                FROM (
                    SELECT job_id
                    FROM dev_marts.fact_job_postings
                    GROUP BY job_id
                    HAVING COUNT(*) > 1
                ) duplicate_jobs
            ) AS duplicate_fact_jobs,

            (
                SELECT COUNT(*)
                FROM (
                    SELECT job_id, skill_id
                    FROM dev_marts.fact_job_skill_mentions
                    GROUP BY job_id, skill_id
                    HAVING COUNT(*) > 1
                ) duplicate_job_skills
            ) AS duplicate_job_skill_pairs,

            (
                SELECT COUNT(*)
                FROM dev_marts.fact_job_postings f
                LEFT JOIN dev_marts.dim_companies c
                    ON f.company_id = c.company_id
                WHERE c.company_id IS NULL
            ) AS orphan_company_refs,

            (
                SELECT COUNT(*)
                FROM dev_marts.fact_job_postings f
                LEFT JOIN dev_marts.dim_roles r
                    ON f.role_id = r.role_id
                WHERE r.role_id IS NULL
            ) AS orphan_role_refs,

            (
                SELECT COUNT(*)
                FROM dev_marts.fact_job_skill_mentions f
                LEFT JOIN dev_marts.fact_job_postings j
                    ON f.job_id = j.job_id
                WHERE j.job_id IS NULL
            ) AS orphan_skill_job_refs,

            (
                SELECT COUNT(*)
                FROM dev_marts.fact_job_skill_mentions f
                LEFT JOIN dev_marts.dim_skills s
                    ON f.skill_id = s.skill_id
                WHERE s.skill_id IS NULL
            ) AS orphan_skill_refs;
    """

    with get_connection() as connection:
        with connection.cursor() as cursor:
            cursor.execute(query)
            row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Sprint 7 validation query returned no rows.")

    return {
        "canonical_jobs": row[0],
        "intermediate_skill_matches": row[1],
        "dim_companies": row[2],
        "dim_skills": row[3],
        "dim_roles": row[4],
        "fact_job_postings": row[5],
        "fact_job_skill_mentions": row[6],
        "duplicate_fact_jobs": row[7],
        "duplicate_job_skill_pairs": row[8],
        "orphan_company_refs": row[9],
        "orphan_role_refs": row[10],
        "orphan_skill_job_refs": row[11],
        "orphan_skill_refs": row[12],
    }


def main() -> None:
    """
    Validate Sprint 7 dimensional warehouse outputs.
    """

    console.print("[bold cyan]Checking Sprint 7 dimensional warehouse...[/bold cyan]")

    try:
        counts = fetch_counts()
    except Exception as exc:
        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 7 validation failed.[/bold red]\n\n"
                    "Could not query Sprint 7 mart models.\n"
                    "Run `make dbt-build` first.\n\n"
                    f"Error: {exc}"
                ),
                title="Sprint 7 Check",
            )
        )
        raise SystemExit(1) from exc

    failures = []

    if counts["canonical_jobs"] == 0:
        failures.append("No canonical jobs found.")

    if counts["dim_companies"] == 0:
        failures.append("dim_companies has no rows.")

    if counts["dim_skills"] == 0:
        failures.append("dim_skills has no rows.")

    if counts["dim_roles"] == 0:
        failures.append("dim_roles has no rows.")

    if counts["fact_job_postings"] != counts["canonical_jobs"]:
        failures.append("fact_job_postings does not match canonical job count.")

    if counts["fact_job_skill_mentions"] != counts["intermediate_skill_matches"]:
        failures.append("fact_job_skill_mentions does not match intermediate skill match count.")

    if counts["duplicate_fact_jobs"] > 0:
        failures.append("Duplicate job_id values found in fact_job_postings.")

    if counts["duplicate_job_skill_pairs"] > 0:
        failures.append("Duplicate job_id x skill_id pairs found.")

    if counts["orphan_company_refs"] > 0:
        failures.append("fact_job_postings contains orphan company_id values.")

    if counts["orphan_role_refs"] > 0:
        failures.append("fact_job_postings contains orphan role_id values.")

    if counts["orphan_skill_job_refs"] > 0:
        failures.append("fact_job_skill_mentions contains orphan job_id values.")

    if counts["orphan_skill_refs"] > 0:
        failures.append("fact_job_skill_mentions contains orphan skill_id values.")

    if failures:
        failure_text = "\n".join(f"- {failure}" for failure in failures)

        console.print(
            Panel.fit(
                (
                    "[bold red]Sprint 7 validation failed.[/bold red]\n\n"
                    f"{failure_text}\n\n"
                    f"Counts:\n"
                    f"{counts}"
                ),
                title="Sprint 7 Check",
            )
        )

        raise SystemExit(1)

    console.print(
        Panel.fit(
            (
                "[bold green]Sprint 7 validation passed.[/bold green]\n\n"
                f"Canonical jobs: {counts['canonical_jobs']}\n"
                f"Companies: {counts['dim_companies']}\n"
                f"Skills: {counts['dim_skills']}\n"
                f"Roles: {counts['dim_roles']}\n"
                f"Job posting facts: {counts['fact_job_postings']}\n"
                f"Job-skill facts: {counts['fact_job_skill_mentions']}\n"
                f"Duplicate jobs: {counts['duplicate_fact_jobs']}\n"
                f"Duplicate job-skill pairs: {counts['duplicate_job_skill_pairs']}\n"
                f"Orphan company refs: {counts['orphan_company_refs']}\n"
                f"Orphan role refs: {counts['orphan_role_refs']}\n"
                f"Orphan skill job refs: {counts['orphan_skill_job_refs']}\n"
                f"Orphan skill refs: {counts['orphan_skill_refs']}"
            ),
            title="Sprint 7 Check",
        )
    )


if __name__ == "__main__":
    main()
