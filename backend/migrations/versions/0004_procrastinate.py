"""procrastinate job queue schema

Revision ID: 0004
Revises: 0003
Create Date: 2026-10-20

The schema SQL is vendored (migrations/sql/procrastinate-<version>.sql) so this revision
never changes when the library is upgraded. Upgrading procrastinate = a new revision that
applies the library's own migration scripts.
"""

from collections.abc import Sequence
from pathlib import Path

from alembic import op
from sqlalchemy.util import await_only

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

SCHEMA_SQL = Path(__file__).parent.parent / "sql" / "procrastinate-3.10.0.sql"


def upgrade() -> None:
    # Multi-statement script with plpgsql bodies: run it through the raw asyncpg
    # connection (no prepared statement, no SQLAlchemy bind-param parsing).
    driver = op.get_bind().connection.driver_connection
    await_only(driver.execute(SCHEMA_SQL.read_text()))  # type: ignore[union-attr]


def downgrade() -> None:
    op.execute(
        """
        DO $$
        DECLARE r record;
        BEGIN
            FOR r IN SELECT tablename FROM pg_tables
                     WHERE schemaname = 'public' AND tablename LIKE 'procrastinate%' LOOP
                EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', r.tablename);
            END LOOP;
            FOR r IN SELECT p.oid::regprocedure AS sig FROM pg_proc p
                     JOIN pg_namespace n ON n.oid = p.pronamespace
                     WHERE n.nspname = 'public' AND p.proname LIKE 'procrastinate%' LOOP
                EXECUTE format('DROP FUNCTION IF EXISTS %s CASCADE', r.sig);
            END LOOP;
            FOR r IN SELECT t.typname FROM pg_type t
                     JOIN pg_namespace n ON n.oid = t.typnamespace
                     WHERE n.nspname = 'public' AND t.typname LIKE 'procrastinate%'
                       AND t.typtype IN ('e', 'c') LOOP  -- enums and composite types
                EXECUTE format('DROP TYPE IF EXISTS %I CASCADE', r.typname);
            END LOOP;
        END $$;
        """
    )
