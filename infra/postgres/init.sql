-- Runs once, only against a freshly-created data directory (empty pgdata
-- volume). The pgvector/pgvector image ships the extension files but does
-- not activate them per-database on its own.

-- Enable on the app database itself. This script connects here by default
-- (the entrypoint runs it against POSTGRES_DB), and the app queries this
-- database directly, so it needs the extension regardless of template1.
CREATE EXTENSION IF NOT EXISTS vector;

-- Also enable on template1: Postgres clones template1 for every future
-- CREATE DATABASE that omits an explicit TEMPLATE, including the
-- disposable test_<name> database Django's test runner creates around
-- every test run. This only benefits databases created AFTER this script
-- runs — it does NOT retroactively affect the app database created above
-- by the entrypoint's own initdb step (verified: without the statement
-- above, the app db would have no vector extension even with this one in
-- place). That's why both statements are needed, not just one.
\c template1
CREATE EXTENSION IF NOT EXISTS vector;
