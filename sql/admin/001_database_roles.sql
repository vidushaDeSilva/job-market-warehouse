-- 001_database_roles.sql
--
-- Sprint 14 database role template.
--
-- Run manually as a database owner/admin.
-- Do not run this through normal make db-init.
--
-- Replace neondb with your database name if different.

-- Group roles.
CREATE ROLE loader_role NOLOGIN;
CREATE ROLE dbt_role NOLOGIN;
CREATE ROLE analytics_readonly_role NOLOGIN;
CREATE ROLE admin_role NOLOGIN;

-- Admin role can inherit operational roles.
GRANT loader_role TO admin_role;
GRANT dbt_role TO admin_role;
GRANT analytics_readonly_role TO admin_role;

-- Allow dbt role to create dbt schemas.
GRANT CONNECT ON DATABASE neondb TO loader_role;
GRANT CONNECT ON DATABASE neondb TO dbt_role;
GRANT CONNECT ON DATABASE neondb TO analytics_readonly_role;

GRANT CREATE ON DATABASE neondb TO dbt_role;

-- Raw and ops access.
GRANT USAGE ON SCHEMA raw TO loader_role, dbt_role;
GRANT USAGE ON SCHEMA ops TO loader_role, dbt_role;

GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA raw TO loader_role;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA ops TO loader_role;

GRANT SELECT ON ALL TABLES IN SCHEMA raw TO dbt_role;
GRANT SELECT ON ALL TABLES IN SCHEMA ops TO dbt_role;

GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA raw TO loader_role;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA ops TO loader_role;

-- Future raw/ops tables.
ALTER DEFAULT PRIVILEGES IN SCHEMA raw
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO loader_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA ops
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO loader_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA raw
GRANT SELECT ON TABLES TO dbt_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA ops
GRANT SELECT ON TABLES TO dbt_role;

-- Analytics readonly access for dbt-produced schemas.
-- Run these after dev/prod schemas exist.
GRANT USAGE ON SCHEMA dev_marts TO analytics_readonly_role;
GRANT SELECT ON ALL TABLES IN SCHEMA dev_marts TO analytics_readonly_role;

GRANT USAGE ON SCHEMA prod_marts TO analytics_readonly_role;
GRANT SELECT ON ALL TABLES IN SCHEMA prod_marts TO analytics_readonly_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA dev_marts
GRANT SELECT ON TABLES TO analytics_readonly_role;

ALTER DEFAULT PRIVILEGES IN SCHEMA prod_marts
GRANT SELECT ON TABLES TO analytics_readonly_role;

-- Example login users.
-- Create real passwords outside Git.
--
-- CREATE USER github_loader_user WITH PASSWORD 'replace-with-secret';
-- CREATE USER github_dbt_user WITH PASSWORD 'replace-with-secret';
-- CREATE USER dashboard_readonly_user WITH PASSWORD 'replace-with-secret';
--
-- GRANT loader_role TO github_loader_user;
-- GRANT dbt_role TO github_dbt_user;
-- GRANT analytics_readonly_role TO dashboard_readonly_user;