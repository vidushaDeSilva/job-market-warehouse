"""
components.py

Reusable Streamlit display helpers.
"""

from __future__ import annotations

import html

import pandas as pd
import streamlit as st


def format_int(value: object) -> str:
    """
    Format integer-like values for metrics.
    """

    if pd.isna(value):
        return "N/A"

    return f"{int(value):,}"


def format_percentage(value: object) -> str:
    """
    Format decimal shares as percentages.
    """

    if pd.isna(value):
        return "N/A"

    return f"{float(value) * 100:.1f}%"


def show_missing_data_warning(message: str) -> None:
    """
    Show a clear warning when data is missing.
    """

    st.warning(message)


def render_adzuna_research_attribution() -> None:
    """
    Render Adzuna source acknowledgement for aggregated analytics.
    """

    st.caption(
        "Data source: The Adzuna API. Metrics are derived from collected "
        "Adzuna job and salary/vacancy data."
    )


def render_adzuna_listing_attribution() -> None:
    """
    Render Adzuna attribution when job-level records are displayed.
    """

    st.markdown(
        """
        <div style="margin-top: 1rem;">
            <a href="https://www.adzuna.co.uk" target="_blank"
               style="
                    display: inline-flex;
                    align-items: center;
                    justify-content: center;
                    width: 116px;
                    height: 23px;
                    border: 1px solid #cccccc;
                    border-radius: 4px;
                    font-size: 14px;
                    font-weight: 700;
                    text-decoration: none;
               ">
                Adzuna
            </a>
            <span style="margin-left: 0.5rem; font-size: 0.85rem;">
                Job listings are sourced from the Adzuna API.
            </span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_job_card(row: pd.Series) -> None:
    """
    Render a job-level card with Adzuna link.
    """

    title = html.escape(str(row.get("job_title") or "Untitled job"))
    company = html.escape(str(row.get("company_name") or "Unknown company"))
    location = html.escape(str(row.get("location_text") or "Unknown location"))
    role = html.escape(str(row.get("role_family") or "unknown"))
    work_mode = html.escape(str(row.get("work_mode") or "unknown"))
    redirect_url = html.escape(str(row.get("redirect_url") or ""))

    salary_midpoint = row.get("salary_midpoint")
    salary_currency = html.escape(str(row.get("salary_currency") or ""))

    if pd.notna(salary_midpoint):
        salary_text = f"{salary_currency} {float(salary_midpoint):,.0f}"
    else:
        salary_text = "Salary not available"

    if redirect_url:
        title_html = f'<a href="{redirect_url}" target="_blank">{title}</a>'
    else:
        title_html = title

    st.markdown(
        f"""
        <div style="
            border: 1px solid #e5e7eb;
            border-radius: 8px;
            padding: 0.9rem;
            margin-bottom: 0.75rem;
        ">
            <div style="font-size: 1.05rem; font-weight: 700;">{title_html}</div>
            <div>{company} · {location}</div>
            <div style="font-size: 0.9rem; color: #555;">
                Role: {role} · Work mode: {work_mode} · {salary_text}
            </div>
            <div style="margin-top: 0.35rem;">
                <a href="https://www.adzuna.co.uk" target="_blank"
                   style="font-size: 0.8rem; font-weight: 700;">
                    Adzuna
                </a>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )