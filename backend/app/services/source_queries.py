"""Source SQL never runs on the application writer connection."""

from contextlib import contextmanager
from functools import lru_cache

import sqlparse
from app.core.config import settings
from sqlalchemy import create_engine, text


@lru_cache(maxsize=4)
def source_engine(url):
    return create_engine(url, pool_pre_ping=True)


@contextmanager
def source_query_batches(query: str, limit: int, batch_size: int):
    statements = sqlparse.parse(query.strip())
    if len(statements) != 1 or statements[0].get_type() != "SELECT":
        raise ValueError("Only one read-only SELECT query is allowed")
    if not settings.source_database_url:
        raise ValueError("SOURCE_DATABASE_URL must configure a restricted source reader")
    sql = str(statements[0]).strip().rstrip(";")
    engine = source_engine(settings.source_database_url)
    with engine.connect() as connection:
        with connection.begin():
            # PostgreSQL enforces read-only even for writable CTEs/functions.
            connection.execute(text("SET TRANSACTION READ ONLY"))
            connection.execute(
                text("SELECT set_config('statement_timeout', :timeout, true)"),
                {"timeout": str(settings.source_query_timeout_ms)},
            )
            connection.execute(
                text("SELECT set_config('lock_timeout', :timeout, true)"),
                {"timeout": str(settings.source_query_timeout_ms)},
            )
            role = connection.execute(
                text("""
                SELECT rolsuper OR rolcreaterole OR rolcreatedb OR rolreplication OR rolbypassrls
                OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member = pg_roles.oid)
                FROM pg_roles WHERE rolname = current_user
            """)
            ).scalar_one()
            if role:
                raise ValueError("Source reader must be unprivileged and have no role memberships")
            # Fail closed if a misconfigured source login can read sensitive application tables.
            for table in (
                "core.users",
                "core.api_keys",
                "core.audit_log",
                "model_registry.model_version",
            ):
                schema, relation = table.split(".")
                if connection.execute(
                    text("""SELECT has_table_privilege(current_user, c.oid, 'SELECT')
                    FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                    WHERE n.nspname = :schema AND c.relname = :relation"""),
                    {"schema": schema, "relation": relation},
                ).scalar_one():
                    raise ValueError("Source reader has forbidden application-table privileges")
            result = connection.execute(
                text(f"SELECT * FROM ({sql}) AS source_preview LIMIT :row_limit").execution_options(
                    yield_per=batch_size
                ),
                {"row_limit": limit},
            )
            try:
                yield list(result.keys()), result.mappings().partitions(batch_size)
            finally:
                result.close()


def execute_source_query(query: str, limit: int):
    with source_query_batches(query, limit, min(limit, 1000)) as (columns, batches):
        return columns, [dict(row) for batch in batches for row in batch]
