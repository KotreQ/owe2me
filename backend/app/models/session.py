import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import BigInt, Timestamp, utcnow_naive


class AuthSession(Base):
    """A logged-in browser session; logout deletes the row."""

    __tablename__ = "sessions"
    __table_args__ = (sa.Index("idx_sessions_account", "account_id"),)

    id: Mapped[int] = mapped_column(BigInt, primary_key=True, autoincrement=True)
    account_id: Mapped[int] = mapped_column(
        BigInt, sa.ForeignKey("accounts.id", ondelete="CASCADE")
    )
    token_hash: Mapped[str] = mapped_column(sa.String(64), unique=True)
    created_at: Mapped[sa.DateTime] = mapped_column(
        Timestamp, default=utcnow_naive, server_default=sa.func.now()
    )
    expires_at: Mapped[sa.DateTime] = mapped_column(Timestamp)
