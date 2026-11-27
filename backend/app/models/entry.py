import enum

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import BigInt, Timestamp, utcnow_naive


class EntryKind(enum.StrEnum):
    debt = "debt"
    payment = "payment"


class EntryStatus(enum.StrEnum):
    pending = "pending"
    accepted = "accepted"
    rejected = "rejected"
    cancelled = "cancelled"


class Entry(Base):
    """One obligation or one cash payment between two accounts.

    `kind='debt'`: payer owes payee `amount_minor`.
    `kind='payment'`: payer paid payee `amount_minor` in cash.

    Only accepted entries count toward balances; `provisional` marks entries
    auto-accepted because the counterparty was a local nickname. Linking that
    nickname to a real account turns them back into pending entries.
    """

    __tablename__ = "entries"
    __table_args__ = (
        sa.CheckConstraint("payer_account_id <> payee_account_id", name="ck_entries_parties"),
        sa.CheckConstraint("amount_minor > 0", name="ck_entries_amount"),
        sa.Index("idx_entries_payer", "payer_account_id", "status"),
        sa.Index("idx_entries_payee", "payee_account_id", "status"),
    )

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    payer_account_id: Mapped[int] = mapped_column(BigInt, sa.ForeignKey("accounts.id"))
    payee_account_id: Mapped[int] = mapped_column(BigInt, sa.ForeignKey("accounts.id"))
    kind: Mapped[EntryKind] = mapped_column(sa.Enum(EntryKind, name="entry_kind"))
    amount_minor: Mapped[int] = mapped_column(BigInt)
    currency: Mapped[str] = mapped_column(sa.CHAR(3))
    title: Mapped[str] = mapped_column(sa.String(120))
    status: Mapped[EntryStatus] = mapped_column(
        sa.Enum(EntryStatus, name="entry_status"), default=EntryStatus.pending
    )
    provisional: Mapped[bool] = mapped_column(default=False)
    created_by_account_id: Mapped[int] = mapped_column(BigInt, sa.ForeignKey("accounts.id"))
    decided_by_account_id: Mapped[int | None] = mapped_column(
        BigInt, sa.ForeignKey("accounts.id"), nullable=True
    )
    decided_at: Mapped[sa.DateTime | None] = mapped_column(Timestamp, nullable=True)
    created_at: Mapped[sa.DateTime] = mapped_column(
        Timestamp, default=utcnow_naive, server_default=sa.func.now()
    )
