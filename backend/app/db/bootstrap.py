"""Idempotent migration, administrator setup, and restricted source login."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from app.core.config import settings
from app.db.seed import seed
from app.db.session import engine
from psycopg2 import sql
from sqlalchemy.engine import make_url


def provision_source_reader():
    if not settings.source_database_url:
        raise ValueError("Set SOURCE_DATABASE_URL to a dedicated source-reader login")
    source = make_url(settings.source_database_url)
    writer = make_url(settings.database_url)
    if not source.username or not source.password or source.username == writer.username:
        raise ValueError("Source reader needs its own login and password")
    if (source.host, source.port, source.database) != (writer.host, writer.port, writer.database):
        raise ValueError(
            "Automatic reader provisioning requires the same database; provision external sources separately"
        )
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (source.username,))
            if not cursor.fetchone():
                cursor.execute(
                    sql.SQL(
                        "CREATE ROLE {} LOGIN PASSWORD %s NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS NOINHERIT"
                    ).format(sql.Identifier(source.username)),
                    (source.password,),
                )
            # Do not silently downgrade/re-purpose an existing privileged login.
            cursor.execute(
                """SELECT rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls
                OR EXISTS (SELECT 1 FROM pg_auth_members WHERE member = pg_roles.oid)
                FROM pg_roles WHERE rolname = %s""",
                (source.username,),
            )
            if cursor.fetchone()[0]:
                raise ValueError("Source reader role has elevated privileges or memberships")
            cursor.execute(
                sql.SQL("ALTER ROLE {} PASSWORD %s").format(sql.Identifier(source.username)),
                (source.password,),
            )
            cursor.execute(
                sql.SQL("GRANT CONNECT ON DATABASE {} TO {}").format(
                    sql.Identifier(writer.database), sql.Identifier(source.username)
                )
            )
            for reference in settings.source_allowed_tables.split(","):
                parts = reference.strip().split(".")
                if len(parts) != 2 or not all(part.isidentifier() for part in parts):
                    raise ValueError(
                        "SOURCE_ALLOWED_TABLES requires comma-separated schema.table identifiers"
                    )
                schema, table = parts
                if schema != "sources" and (schema, table) != ("feature_store", "sample_events"):
                    raise ValueError(
                        "Source tables must be in sources schema, or feature_store.sample_events"
                    )
                cursor.execute(
                    sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(
                        sql.Identifier(schema), sql.Identifier(source.username)
                    )
                )
                cursor.execute(
                    sql.SQL("GRANT SELECT ON TABLE {}.{} TO {}").format(
                        sql.Identifier(schema),
                        sql.Identifier(table),
                        sql.Identifier(source.username),
                    )
                )
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def bootstrap():
    root = Path(__file__).resolve().parents[2]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "alembic"))
    command.upgrade(config, "head")
    seed(include_demo=settings.seed_demo_data)
    provision_source_reader()


if __name__ == "__main__":
    bootstrap()
