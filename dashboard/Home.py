"""
Home.py

Job Market Overview dashboard page.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

from components import (
    format_int,
    format_percentage,
    render_adzuna_research_attribution,
    show_missing_data_warning,
)
from db import marts_table, run_query

st.set_page_config(
    page_title="Job Market Overview",
    page_icon="📊",
    layout="wide",
)

st.title("Job Market Overview")

render_adzuna_research_attribution()

overview_table = marts_table("mart_job_market_overview")
health_table = marts_table("mart_pipeline_health")
skill_table = marts_table("mart_skill_demand_weekly")
company_table = marts_table("mart_company_hiring_summary")
role_table = marts_table("mart_role_market_summary")
salary_table = marts_table("mart_salary_distribution")

overview = run_query(f"SELECT * FROM {overview_table} LIMIT 1")
health = run_query(f"SELECT * FROM {health_table} LIMIT 1")

if overview.empty:
    show_missing_data_warning(
        "No overview data is available yet. Run dbt build before opening the dashboard."
    )
    st.stop()

if not health.empty:
    health_status = health.loc[0, "pipeline_health_status"]

    if health_status != "healthy":
        st.warning(f"Current pipeline health status: {health_status}")

row = overview.loc[0]

metric_cols = st.columns(4)

metric_cols[0].metric("Total unique jobs", format_int(row["total_unique_jobs"]))
metric_cols[1].metric(
    "Jobs collected this week",
    format_int(row["jobs_collected_this_week"]),
)
metric_cols[2].metric("Remote share", format_percentage(row["remote_share"]))
metric_cols[3].metric("Salary coverage", format_percentage(row["salary_coverage"]))

st.divider()

left_col, right_col = st.columns(2)

with left_col:
    st.subheader("Top skills")

    top_skills = run_query(
        f"""
        SELECT
            skill_name,
            SUM(unique_job_count)::integer AS unique_job_count
        FROM {skill_table}
        GROUP BY skill_name
        ORDER BY unique_job_count DESC, skill_name
        LIMIT 15;
        """
    )

    if top_skills.empty:
        show_missing_data_warning("No skill demand data available yet.")
    else:
        st.bar_chart(top_skills, x="skill_name", y="unique_job_count")

with right_col:
    st.subheader("Top hiring companies")

    top_companies = run_query(
        f"""
        SELECT
            company_name,
            job_count
        FROM {company_table}
        ORDER BY job_count DESC, company_name
        LIMIT 15;
        """
    )

    if top_companies.empty:
        show_missing_data_warning("No company hiring data available yet.")
    else:
        st.bar_chart(top_companies, x="company_name", y="job_count")

st.divider()

st.subheader("Skill demand over time")

skill_trend = run_query(
    f"""
    WITH top_skills AS (
        SELECT
            skill_id,
            skill_name,
            SUM(unique_job_count) AS total_jobs
        FROM {skill_table}
        GROUP BY skill_id, skill_name
        ORDER BY total_jobs DESC
        LIMIT 5
    )

    SELECT
        m.week_start_date,
        t.skill_name,
        m.unique_job_count
    FROM {skill_table} m
    INNER JOIN top_skills t
        ON m.skill_id = t.skill_id
    ORDER BY m.week_start_date, t.skill_name;
    """
)

if skill_trend.empty:
    show_missing_data_warning("No weekly skill trend data available yet.")
else:
    pivot = skill_trend.pivot_table(
        index="week_start_date",
        columns="skill_name",
        values="unique_job_count",
        aggfunc="sum",
    ).fillna(0)

    st.line_chart(pivot)

st.divider()

left_col, right_col = st.columns(2)

with left_col:
    st.subheader("Role distribution")

    role_distribution = run_query(
        f"""
        SELECT
            role_family,
            job_count
        FROM {role_table}
        ORDER BY job_count DESC, role_family;
        """
    )

    if role_distribution.empty:
        show_missing_data_warning("No role distribution data available yet.")
    else:
        st.bar_chart(role_distribution, x="role_family", y="job_count")

with right_col:
    st.subheader("Salary distribution")

    salary_distribution = run_query(
        f"""
        SELECT
            salary_currency,
            salary_bucket,
            salary_bucket_sort,
            job_count
        FROM {salary_table}
        ORDER BY salary_currency, salary_bucket_sort;
        """
    )

    if salary_distribution.empty:
        show_missing_data_warning("No salary distribution data available yet.")
    else:
        selected_currency = st.selectbox(
            "Currency",
            sorted(salary_distribution["salary_currency"].unique()),
        )

        filtered_salary = salary_distribution[
            salary_distribution["salary_currency"] == selected_currency
        ]

        st.bar_chart(filtered_salary, x="salary_bucket", y="job_count")

st.divider()

st.caption(
    "Dashboard queries are cached. If data looks stale, refresh after the next "
    "successful pipeline run."
)