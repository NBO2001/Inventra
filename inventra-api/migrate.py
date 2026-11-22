"""Apply pending PostgreSQL schema migrations in filename order."""

import os
from pathlib import Path

import psycopg

MIGRATIONS = Path(__file__).resolve().parent / "migrations"
DEFAULT_URL = "postgresql://inventra:inventra@127.0.0.1:5432/inventra"


def migrate(database_url=None):
    files = sorted(MIGRATIONS.glob("[0-9][0-9][0-9]_*.sql"))
    with psycopg.connect(
        database_url or os.environ.get("DATABASE_URL", DEFAULT_URL)
    ) as conn:
        with conn.transaction():
            conn.execute("SELECT pg_advisory_xact_lock(51239801)")
            conn.execute("""CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
            )""")
            applied = {
                row[0] for row in conn.execute("SELECT version FROM schema_migrations")
            }
            for path in files:
                if path.name in applied:
                    continue
                conn.execute(path.read_text())
                conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (path.name,),
                )
                print(f"Applied {path.name}")


if __name__ == "__main__":
    migrate()
