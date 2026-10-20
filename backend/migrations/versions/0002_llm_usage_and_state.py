"""llm usage and state

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-20 10:42:46.313589
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "llm_state",
        sa.Column("provider", sa.String(length=32), nullable=False),
        sa.Column("paused_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pause_streak", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("provider", name=op.f("pk_llm_state")),
    )
    op.create_table(
        "llm_usage",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=16), nullable=False),
        sa.Column("day", sa.Date(), nullable=False),
        sa.Column("count", sa.Integer(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_llm_usage_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_llm_usage")),
        sa.UniqueConstraint("user_id", "kind", "day", name=op.f("uq_llm_usage_user_kind_day")),
    )


def downgrade() -> None:
    op.drop_table("llm_usage")
    op.drop_table("llm_state")
