-- Runs once, only when the Postgres data volume is first initialized
-- (official postgres image behavior for /docker-entrypoint-initdb.d/*.sql).
-- Creates a separate database for integration/API/e2e tests so test runs
-- never touch the primary demo database.
CREATE DATABASE archguard_test;
