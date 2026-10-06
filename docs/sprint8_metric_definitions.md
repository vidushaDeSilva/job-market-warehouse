# Sprint 8 — Metric Definitions

This document defines the analytical metrics exposed by the Sprint 8 marts.

All metrics are calculated using **canonical (deduplicated) job postings** unless explicitly stated otherwise.

---

# mart_skill_demand_weekly

## Grain

One row per:

```
week_start_date × skill_id
```

## Columns

### week_start_date

The Monday-starting week derived from `fact_job_postings.first_seen_at`.

### skill_id

Unique identifier of the skill from `dim_skills`.

### skill_name

Normalized skill name.

### skill_category

Category assigned to the skill.

### unique_job_count

Number of canonical job postings first observed during the week that mention the skill.

### total_unique_jobs_in_week

Total number of canonical job postings first observed during the week.

### share_of_jobs

Ratio of `unique_job_count` to `total_unique_jobs_in_week`.

---

# mart_company_hiring_summary

## Grain

One row per:

```
company_id
```

## Columns

### company_id

Unique identifier of the company from `dim_companies`.

### company_name

Human-readable company name.

### job_count

Number of canonical job postings associated with the company.

### data_engineering_jobs

Number of canonical job postings classified as `data_engineering`.

### analytics_engineering_jobs

Number of canonical job postings classified as `analytics_engineering`.

### remote_jobs

Number of canonical job postings classified as `remote`.

### jobs_with_salary

Number of canonical job postings with available salary information.

### salary_coverage

Ratio of `jobs_with_salary` to `job_count`.

### remote_share

Ratio of `remote_jobs` to `job_count`.

### first_seen_at

Earliest observation timestamp among the company's canonical job postings.

### last_seen_at

Latest observation timestamp among the company's canonical job postings.

---

# mart_role_market_summary

## Grain

One row per:

```
role_family
```

## Columns

### role_family

Standardized role category.

### job_count

Number of canonical job postings belonging to the role family.

### jobs_with_salary

Number of canonical job postings with available salary information.

### median_salary

Median value of `salary_midpoint` for canonical job postings with available salary information.

### salary_coverage

Ratio of `jobs_with_salary` to `job_count`.

### remote_jobs

Number of canonical job postings classified as remote.

### remote_share

Ratio of `remote_jobs` to `job_count`.

### top_skill_id

Identifier of the most frequently mentioned skill within the role family.

### top_skill_name

Most frequently mentioned skill within the role family.

### top_skill_job_count

Number of canonical job postings mentioning the top skill.

### top_skill_share

Ratio of `top_skill_job_count` to `job_count`.

### first_seen_at

Earliest observation timestamp among canonical job postings in the role family.

### last_seen_at

Latest observation timestamp among canonical job postings in the role family.