"""
1_Data_Health.py

Operational data health dashboard page.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components import format_int, format_percentage, show_missing_data_warning
from db import marts_table, run_query

st.set_page_config(
    page_title="Data Health",
    page_icon="🩺",
    layout="wide",
)

st.title("Data Health")

health_table = marts_table("mart_pipeline_health")
quality_table = marts_table("mart_data_quality_summary")
batch_table = marts_table("mart_ingestion_batch_summary")
api_table = marts_table("mart_api_request_summary")

health = run_query(f"SELECT * FROM {health_table} LIMIT 1")
quality = run_query(f"SELECT * FROM {quality_table} LIMIT 1")

if health.empty:
    show_missing_data_warning("No pipeline health data available yet.")
    st.stop()

row = health.loc[0]


def calculate_quality_score(health_row: pd.Series) -> int:
    """
    Calculate a simple dashboard-level data quality score.
    """

    score = 100

    penalty_rules = {
        "stale_collection_warning": 25,
        "records_drop_warning": 15,
        "api_429_warning": 15,
        "dbt_test_failure_warning": 25,
        "duplicate_rate_warning": 10,
        "low_skill_extraction_warning": 10,
        "high_unknown_role_warning": 5,
    }

    for column, penalty in penalty_rules.items():
        if bool(health_row.get(column, False)):
            score -= penalty

    return max(score, 0)


score = calculate_quality_score(row)

metric_cols = st.columns(4)

metric_cols[0].metric("Pipeline health", str(row["pipeline_health_status"]))
metric_cols[1].metric("Data quality score", f"{score}/100")
metric_cols[2].metric(
    "Hours since successful ingestion",
    "N/A"
    if pd.isna(row["hours_since_last_successful_ingestion"])
    else f"{float(row['hours_since_last_successful_ingestion']):.1f}",
)
metric_cols[3].metric("Latest API failures", format_int(row["latest_api_failure_count"]))

st.divider()

left_col, right_col = st.columns(2)

with left_col:
    st.subheader("Last pipeline run")

    st.write(
        {
            "latest_pipeline_status": row["latest_pipeline_status"],
            "latest_pipeline_started_at": row["latest_pipeline_started_at"],
            "latest_pipeline_finished_at": row["latest_pipeline_finished_at"],
            "last_successful_pipeline_finished_at": row[
                "last_successful_pipeline_finished_at"
            ],
            "dbt_invocation_id": row["dbt_invocation_id"],
            "tests_passed": row["tests_passed"],
            "tests_failed": row["tests_failed"],
            "git_sha": row["git_sha"],
        }
    )

with right_col:
    st.subheader("Latest ingestion")

    st.write(
        {
            "latest_ingestion_batch_status": row["latest_ingestion_batch_status"],
            "latest_ingestion_started_at": row["latest_ingestion_started_at"],
            "latest_ingestion_finished_at": row["latest_ingestion_finished_at"],
            "last_successful_ingestion_finished_at": row[
                "last_successful_ingestion_finished_at"
            ],
            "latest_records_received": row["latest_records_received"],
            "latest_records_loaded": row["latest_records_loaded"],
            "latest_records_quarantined": row["latest_records_quarantined"],
        }
    )

st.divider()

st.subheader("Warning flags")

warnings = {
    "Stale collection": row["stale_collection_warning"],
    "Records dropped >50%": row["records_drop_warning"],
    "API 429 encountered": row["api_429_warning"],
    "dbt test failure": row["dbt_test_failure_warning"],
    "Duplicate rate high": row["duplicate_rate_warning"],
    "Low skill extraction": row["low_skill_extraction_warning"],
    "High unknown role share": row["high_unknown_role_warning"],
}

warning_df = pd.DataFrame(
    [{"warning": key, "active": bool(value)} for key, value in warnings.items()]
)

st.dataframe(warning_df, use_container_width=True, hide_index=True)

st.divider()

st.subheader("Data quality metrics")

if quality.empty:
    show_missing_data_warning("No data quality summary available yet.")
else:
    q = quality.loc[0]

    quality_cols = st.columns(4)

    quality_cols[0].metric(
        "Duplicate percentage",
        format_percentage(q["duplicate_percentage"]),
    )
    quality_cols[1].metric("Salary coverage", format_percentage(q["salary_coverage"]))
    quality_cols[2].metric(
        "Skill extraction coverage",
        format_percentage(q["skill_extraction_coverage"]),
    )
    quality_cols[3].metric(
        "Unknown role share",
        format_percentage(q["unknown_role_share"]),
    )

st.divider()

left_col, right_col = st.columns(2)

with left_col:
    st.subheader("Recent ingestion batches")

    batches = run_query(
        f"""
        SELECT
            batch_started_at,
            batch_status,
            records_received,
            records_loaded,
            records_quarantined,
            api_failure_count,
            records_drop_warning,
            api_429_warning,
            quarantine_rate_warning
        FROM {batch_table}
        ORDER BY batch_started_at DESC
        LIMIT 10;
        """
    )

    st.dataframe(batches, use_container_width=True, hide_index=True)

with right_col:
    st.subheader("Recent API request summaries")

    api_summary = run_query(
        f"""
        SELECT
            batch_started_at,
            batch_status,
            api_requests_made,
            api_success_count,
            api_failure_count,
            api_failure_rate,
            api_rate_limit_hit,
            api_warning
        FROM {api_table}
        ORDER BY batch_started_at DESC
        LIMIT 10;
        """
    )

    st.dataframe(api_summary, use_container_width=True, hide_index=True)