"""per-user default currency

Revision ID: 0003_user_currency
Revises: 0002_sessions
Create Date: 2026-11-27

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0003_user_currency"
down_revision: str | None = "0002_sessions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("default_currency", sa.CHAR(3), nullable=True))
    op.execute("UPDATE users SET default_currency = 'PLN' WHERE default_currency IS NULL")
    op.alter_column(
        "users",
        "default_currency",
        existing_type=sa.CHAR(3),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("users", "default_currency")
