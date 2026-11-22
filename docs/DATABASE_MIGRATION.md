# Database Migration Rules: MS SQL Server → Supabase PostgreSQL

This document records all decisions, type mappings, and rules applied when migrating the Feature Store & Model Registry from Microsoft SQL Server 2022 to Supabase PostgreSQL (PostgreSQL 15+).

---

## Overview

| Attribute          | Before (MS SQL Server)                     | After (Supabase PostgreSQL)                      |
|--------------------|--------------------------------------------|--------------------------------------------------|
| Database Engine    | Microsoft SQL Server 2022                  | Supabase PostgreSQL 15+                          |
| Hosting            | Docker container (local, port 1433)        | Supabase cloud (managed, port 5432)              |
| Python Driver      | `pyodbc` + ODBC Driver 18 for SQL Server   | `psycopg2-binary`                                |
| SQLAlchemy Dialect | `mssql+pyodbc://...`                       | `postgresql+psycopg2://...`                      |
| Docker Dependency  | Required (`mcr.microsoft.com/mssql`)       | Not required (cloud-hosted)                      |
| SQLAlchemy Dialect | `sqlalchemy.dialects.mssql.UNIQUEIDENTIFIER` | `sqlalchemy.dialects.postgresql.UUID`          |

---

## Data Type Mapping

| MS SQL Server Type       | PostgreSQL Equivalent  | Notes                                                         |
|--------------------------|------------------------|---------------------------------------------------------------|
| `UNIQUEIDENTIFIER`       | `UUID`                 | PostgreSQL native UUID type                                   |
| `NEWID()`                | `gen_random_uuid()`    | Requires `pgcrypto` extension (included in `schema.sql`)      |
| `NVARCHAR(n)`            | `VARCHAR(n)`           | PostgreSQL stores all strings as UTF-8 natively               |
| `NVARCHAR(MAX)`          | `TEXT`                 | Unbounded text — no size limit                                |
| `DATETIME2`              | `TIMESTAMPTZ`          | Timezone-aware timestamp (best practice in PostgreSQL)        |
| `SYSUTCDATETIME()`       | `NOW()`                | Returns current UTC timestamp                                 |
| `DATEADD(day, -N, ...)`  | `NOW() - INTERVAL 'N days'` | Standard SQL interval syntax                             |
| `BIT`                    | `BOOLEAN`              | Use `true`/`false` literals (not `1`/`0`)                     |
| `DECIMAL(12,2)`          | `NUMERIC(12,2)`        | Direct equivalent                                             |
| `INT`                    | `INTEGER`              | Direct equivalent                                             |

---

## Schema Handling

PostgreSQL supports schemas natively, identical to MS SQL Server. The same 4 schemas are preserved:

| Schema           | Purpose                                                     |
|------------------|-------------------------------------------------------------|
| `core`           | Users, roles, user_roles, audit_log, api_keys               |
| `feature_store`  | Feature groups, definitions, lineage, materialization, values |
| `model_registry` | Models, versions, lineage, stage history                    |
| `jobs`           | Job definitions and run logs                                |

**Key change**: Schema creation syntax differs:

| MS SQL Server                                                               | PostgreSQL                        |
|-----------------------------------------------------------------------------|-----------------------------------|
| `IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE name = 'x') EXEC('CREATE SCHEMA x')` | `CREATE SCHEMA IF NOT EXISTS x` |

---

## SQL Syntax Changes

| MS SQL Server Syntax                                | PostgreSQL Equivalent                             |
|-----------------------------------------------------|---------------------------------------------------|
| `IF OBJECT_ID('schema.table', 'U') IS NULL CREATE TABLE ...` | `CREATE TABLE IF NOT EXISTS schema.table (...)`  |
| `IF NOT EXISTS (SELECT 1 FROM sys.schemas WHERE ...)` | `CREATE SCHEMA IF NOT EXISTS`                   |
| `SYSUTCDATETIME()`                                  | `NOW()`                                           |
| `DATEADD(day, -1, SYSUTCDATETIME())`                | `NOW() - INTERVAL '1 day'`                        |
| `NEWID()`                                           | `gen_random_uuid()`                               |
| `NVARCHAR(MAX)`                                     | `TEXT`                                            |
| `BIT NOT NULL DEFAULT 1`                            | `BOOLEAN NOT NULL DEFAULT TRUE`                   |
| `GO` (batch separator)                              | Removed — not needed in PostgreSQL                |
| `mssql.UNIQUEIDENTIFIER` (SQLAlchemy)               | `postgresql.UUID(as_uuid=True)` (SQLAlchemy)      |
| `server_default=sa.text("SYSUTCDATETIME()")`        | `server_default=sa.text("now()")`                 |
| `server_default=sa.text("NEWID()")`                 | `server_default=sa.text("gen_random_uuid()")`     |
| `server_default=sa.text("1")` (BIT)                 | `server_default=sa.text("true")` (BOOLEAN)        |

---

## Files Changed

| File                                                            | Change Summary                                                                         |
|-----------------------------------------------------------------|----------------------------------------------------------------------------------------|
| `backend/app/db/models/core.py`                                 | `UNIQUEIDENTIFIER` → `UUID`; `sysutcdatetime()` → `now()`; `text("1")` → `text("true")` |
| `backend/app/db/models/feature_store.py`                        | Same dialect swap as above                                                             |
| `backend/app/db/models/model_registry.py`                       | Same dialect swap as above                                                             |
| `backend/app/db/models/jobs.py`                                 | Same dialect swap as above                                                             |
| `backend/app/core/config.py`                                    | `mssql+pyodbc://...` → `postgresql+psycopg2://...` Supabase connection string         |
| `backend/app/db/seed.py`                                        | T-SQL `OBJECT_ID`, `IF NOT EXISTS (SELECT 1...)`, `SYSUTCDATETIME()`, `DATEADD()` → PostgreSQL equivalents |
| `backend/requirements.txt`                                      | Removed `pyodbc`; added `psycopg2-binary`                                              |
| `backend/alembic/versions/0001_initial.py`                      | Full rewrite: `postgresql.UUID`, `gen_random_uuid()`, `now()`, PostgreSQL schema DDL  |
| `backend/alembic/versions/c035ccd4da68_add_api_key_model.py`    | Rewritten with `postgresql.UUID` and `gen_random_uuid()`                               |
| `backend/alembic/versions/2326743abe1f_add_validation_rules.py` | No change needed — dialect-agnostic `op.add_column` with `sa.Text()`                  |
| `backend/alembic/versions/05dd462a6641_add_environment.py`      | No change needed — dialect-agnostic `op.add_column` with `sa.String()`                |
| `backend/alembic.ini`                                           | `sqlalchemy.url` placeholder updated to `postgresql+psycopg2://user:password@host/dbname` |
| `backend/alembic/env.py`                                        | No change needed — `include_schemas=True` works for both dialects                     |
| `database/schema.sql`                                           | Full rewrite from T-SQL to PostgreSQL (`UUID`, `TIMESTAMPTZ`, `IF NOT EXISTS`, `pgcrypto`) |
| `docker-compose.yml`                                            | MS SQL Server container replaced with commented-out local PostgreSQL reference        |
| `.env.example`                                                  | Created at project root with Supabase `DATABASE_URL` template and all env vars        |
| `README.md`                                                     | All references updated: Supabase prerequisites, new quickstart, updated architecture diagram |
| `docs/DATABASE_MIGRATION.md`                                    | This file — full migration rules, type mapping, and change log                        |

---

## Alembic Migration Notes

- The `include_schemas=True` option in `alembic/env.py` is preserved — it works identically for both MS SQL Server and PostgreSQL.
- When running `alembic upgrade head` against Supabase, the `0001_initial` migration handles schema creation via `CREATE SCHEMA IF NOT EXISTS`.
- **Do not run** `alembic upgrade head` against a Supabase DB that was already initialised via the SQL Editor — it will conflict. Choose **one** approach (Alembic **or** SQL Editor).
- The Alembic migration chain order: `0001_initial` → `c035ccd4da68` → `2326743abe1f` → `05dd462a6641`.

---

## Environment Variable Setup

Set the following in `backend/.env` (copy from `.env.example`):

```env
DATABASE_URL=postgresql+psycopg2://postgres.YOUR_PROJECT_REF:YOUR_PASSWORD@aws-0-REGION.pooler.supabase.com:5432/postgres
```

Get this connection string from: **Supabase Dashboard → Project Settings → Database → Connection string (Python/SQLAlchemy)**.

---

## Supabase Connection Pooler Notes

Supabase provides two connection modes:

| Mode                | Port   | Best For                                      | SQLAlchemy Note                         |
|---------------------|--------|-----------------------------------------------|-----------------------------------------|
| Transaction pooler  | `6543` | Serverless / short-lived connections          | Add `?pgbouncer=true` to the URL        |
| Session pooler      | `5432` | Persistent connections (FastAPI + Uvicorn)    | **Recommended for this project**        |

Use **port `5432`** (Session pooler) in your `DATABASE_URL`.

---

## Rules & Decisions

1. **UUID primary keys preserved**: All PKs remain `UUID` for consistency. Supabase supports UUID natively — no change to the data model.
2. **Timezone-aware timestamps**: `TIMESTAMPTZ` (timezone-aware) is used throughout instead of plain `TIMESTAMP`, following PostgreSQL best practices.
3. **pgcrypto extension**: `CREATE EXTENSION IF NOT EXISTS "pgcrypto"` is included in `schema.sql` to enable `gen_random_uuid()`. This is pre-installed on all Supabase projects.
4. **Explicit schema arguments**: SQLAlchemy models use `__table_args__ = {"schema": "..."}`, which works identically in PostgreSQL — no `search_path` override is needed.
5. **psycopg2-binary for portability**: Used instead of compiled `psycopg2` for simpler cross-platform installation. Consider switching to `psycopg2` (non-binary) in production for better performance.
6. **Local development fallback**: A commented-out local PostgreSQL `docker-compose.yml` service is provided for developers who prefer to test without a Supabase account.
7. **No MSSQL syntax in codebase**: All MS SQL-specific syntax (`UNIQUEIDENTIFIER`, `pyodbc`, `SYSUTCDATETIME`, `OBJECT_ID`, `DATEADD`, `mssql` dialect imports, `GO` separator) has been removed from all files.
