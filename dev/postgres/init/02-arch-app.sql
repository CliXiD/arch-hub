-- Runs once on an empty data volume (dev/bin/stack reset to re-run). [ADR-0014]
-- Runtime role for arch-api: DML only. Migrations (as `arch`) grant it table rights; on
-- change_log it only gets SELECT and INSERT. Dummy local password.
CREATE ROLE arch_app LOGIN PASSWORD 'arch_app';
GRANT CONNECT ON DATABASE arch TO arch_app;
GRANT USAGE ON SCHEMA public TO arch_app;
