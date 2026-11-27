"""initial ledger schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-11-27

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "0001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column(
            "kind",
            sa.Enum("user", "local", name="account_kind"),
            nullable=False,
        ),
        sa.Column("display_name", sa.String(length=100), nullable=False),
        sa.Column("owner_account_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            mysql.DATETIME(fsp=6),
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "(kind = 'local' AND owner_account_id IS NOT NULL) OR "
            "(kind = 'user' AND owner_account_id IS NULL)",
            name="ck_accounts_owner",
        ),
        sa.ForeignKeyConstraint(["owner_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("owner_account_id", "display_name", name="uq_accounts_owner_name"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id"),
        sa.UniqueConstraint("username"),
    )

    op.create_table(
        "entries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("payer_account_id", sa.BigInteger(), nullable=False),
        sa.Column("payee_account_id", sa.BigInteger(), nullable=False),
        sa.Column("kind", sa.Enum("debt", "payment", name="entry_kind"), nullable=False),
        sa.Column("amount_minor", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.CHAR(length=3), nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "accepted", "rejected", "cancelled", name="entry_status"),
            nullable=False,
        ),
        sa.Column("provisional", sa.Boolean(), nullable=False),
        sa.Column("created_by_account_id", sa.BigInteger(), nullable=False),
        sa.Column("decided_by_account_id", sa.BigInteger(), nullable=True),
        sa.Column("decided_at", mysql.DATETIME(fsp=6), nullable=True),
        sa.Column(
            "created_at",
            mysql.DATETIME(fsp=6),
            server_default=sa.text("CURRENT_TIMESTAMP(6)"),
            nullable=False,
        ),
        sa.CheckConstraint("payer_account_id <> payee_account_id", name="ck_entries_parties"),
        sa.CheckConstraint("amount_minor > 0", name="ck_entries_amount"),
        sa.ForeignKeyConstraint(["payer_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["payee_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["created_by_account_id"], ["accounts.id"]),
        sa.ForeignKeyConstraint(["decided_by_account_id"], ["accounts.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_entries_payer", "entries", ["payer_account_id", "status"])
    op.create_index("idx_entries_payee", "entries", ["payee_account_id", "status"])


def downgrade() -> None:
    op.drop_table("entries")
    op.drop_table("users")
    op.drop_table("accounts")
