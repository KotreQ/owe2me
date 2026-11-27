import enum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import BigInt, Timestamp, utcnow_naive


class AccountKind(enum.StrEnum):
    user = "user"
    local = "local"


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        sa.CheckConstraint(
            "(kind = 'local' AND owner_account_id IS NOT NULL) OR "
            "(kind = 'user' AND owner_account_id IS NULL)",
            name="ck_accounts_owner",
        ),
        sa.UniqueConstraint("owner_account_id", "display_name", name="uq_accounts_owner_name"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    kind: Mapped[AccountKind] = mapped_column(sa.Enum(AccountKind, name="account_kind"))
    display_name: Mapped[str] = mapped_column(sa.String(100))
    owner_account_id: Mapped[int | None] = mapped_column(
        BigInt, sa.ForeignKey("accounts.id"), nullable=True
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        Timestamp, default=utcnow_naive, server_default=sa.func.now()
    )
    updated_at: Mapped[sa.DateTime] = mapped_column(
        Timestamp, default=utcnow_naive, onupdate=utcnow_naive, server_default=sa.func.now()
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(BigInt, sa.ForeignKey("accounts.id"), unique=True)
    username: Mapped[str] = mapped_column(sa.String(50), unique=True)
    password_hash: Mapped[str] = mapped_column(sa.String(255))
    default_currency: Mapped[str] = mapped_column(sa.CHAR(3))
    created_at: Mapped[sa.DateTime] = mapped_column(
        Timestamp, default=utcnow_naive, server_default=sa.func.now()
    )
