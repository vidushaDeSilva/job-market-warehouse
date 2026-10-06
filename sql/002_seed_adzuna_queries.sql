/*
002_seed_adzuna_queries.sql

Adds initial Adzuna search configurations.

The INSERT uses ON CONFLICT DO NOTHING so the script is idempotent:
running database initialization repeatedly will not create duplicate
query configurations.
*/


-- Primary query used when Sprint 2 starts.
INSERT INTO raw.adzuna_query_config (
    country_code,
    keyword,
    location,
    results_per_page,
    max_pages,
    is_active,
    description
)
VALUES (
    'gb',
    'data engineer',
    'London',
    50,
    2,
    TRUE,
    'Primary development query used while building the ingestion pipeline.'
)
ON CONFLICT (country_code, keyword, location)
DO NOTHING;


-- Additional queries are prepared but disabled so that they do not consume
-- API quota until we intentionally enable them.
INSERT INTO raw.adzuna_query_config (
    country_code,
    keyword,
    location,
    results_per_page,
    max_pages,
    is_active,
    description
)
VALUES
(
    'gb',
    'analytics engineer',
    'London',
    50,
    2,
    FALSE,
    'Additional analytics engineering query.'
),
(
    'it',
    'data engineer',
    'Rome',
    50,
    2,
    FALSE,
    'Italian job-market query for later use.'
)
ON CONFLICT (country_code, keyword, location)
DO NOTHING;