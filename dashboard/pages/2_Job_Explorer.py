"""
2_Job_Explorer.py

Optional job-level explorer.

Because this page displays job-level records, Adzuna attribution is shown.
"""

from __future__ import annotations

import streamlit as st
from components import (
    render_adzuna_listing_attribution,
    render_adzuna_research_attribution,
    render_job_card,
    show_missing_data_warning,
)
from db import marts_table, run_query

st.set_page_config(
    page_title="Job Explorer",
    page_icon="🔎",
    layout="wide",
)

st.title("Job Explorer")

render_adzuna_research_attribution()
render_adzuna_listing_attribution()

fact_table = marts_table("fact_job_postings")

filters = run_query(
    f"""
    SELECT
        ARRAY_AGG(DISTINCT role_family ORDER BY role_family) AS role_families,
        ARRAY_AGG(DISTINCT work_mode ORDER BY work_mode) AS work_modes
    FROM {fact_table};
    """
)

role_options = []
work_mode_options = []

if not filters.empty:
    role_options = [value for value in filters.loc[0, "role_families"] if value]
    work_mode_options = [value for value in filters.loc[0, "work_modes"] if value]

left_col, right_col, third_col = st.columns(3)

selected_role = left_col.selectbox("Role family", ["All", *role_options])
selected_work_mode = right_col.selectbox("Work mode", ["All", *work_mode_options])
search_text = third_col.text_input("Title/company search", "")

where_clauses = ["1 = 1"]
params: list[str] = []

if selected_role != "All":
    where_clauses.append("role_family = %s")
    params.append(selected_role)

if selected_work_mode != "All":
    where_clauses.append("work_mode = %s")
    params.append(selected_work_mode)

if search_text.strip():
    where_clauses.append(
        "(LOWER(job_title) LIKE LOWER(%s) OR LOWER(company_name) LIKE LOWER(%s))"
    )
    params.extend([f"%{search_text.strip()}%", f"%{search_text.strip()}%"])

where_sql = " AND ".join(where_clauses)

jobs = run_query(
    f"""
    SELECT
        job_id,
        job_title,
        company_name,
        location_text,
        redirect_url,
        role_family,
        work_mode,
        salary_midpoint,
        salary_currency,
        latest_collected_at
    FROM {fact_table}
    WHERE {where_sql}
    ORDER BY latest_collected_at DESC NULLS LAST
    LIMIT 30;
    """,
    tuple(params),
)

if jobs.empty:
    show_missing_data_warning("No jobs match the selected filters.")
    st.stop()

st.caption(f"Showing {len(jobs)} job records. Job links go through Adzuna redirect URLs.")

for _, row in jobs.iterrows():
    render_job_card(row)