from datetime import UTC, datetime

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

BigInt = sa.BigInteger().with_variant(sa.Integer(), "sqlite")
Timestamp = sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def utcnow_naive() -> datetime:
    """UTC now without tzinfo, for naive DATETIME columns."""
    return datetime.now(UTC).replace(tzinfo=None)
