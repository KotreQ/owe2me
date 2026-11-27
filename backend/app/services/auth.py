import re
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.security import (
    DUMMY_HASH,
    hash_password,
    new_session_token,
    token_digest,
    verify_password,
)
from app.db.types import utcnow_naive
from app.models import Account, AccountKind, AuthSession, User

USERNAME_PATTERN = re.compile(r"^[a-z0-9_.-]{3,50}$")
PASSWORD_MIN_LENGTH = 8
PASSWORD_MAX_LENGTH = 128

settings = get_settings()


class AuthError(Exception):
    """Base class for expected authentication failures."""


class UsernameTaken(AuthError):
    pass


class InvalidCredentials(AuthError):
    pass


class InvalidSession(AuthError):
    pass


def normalize_username(username: str) -> str:
    return username.strip().lower()


def validate_credentials(username: str, password: str) -> str:
    normalized = normalize_username(username)
    if not USERNAME_PATTERN.fullmatch(normalized):
        raise AuthError("username must be 3-50 characters of a-z, 0-9, dot, dash or underscore")
    if not PASSWORD_MIN_LENGTH <= len(password) <= PASSWORD_MAX_LENGTH:
        raise AuthError(f"password must be between {PASSWORD_MIN_LENGTH} and {PASSWORD_MAX_LENGTH}")
    return normalized


def signup(
    db: Session, *, username: str, password: str, display_name: str | None = None
) -> tuple[User, str]:
    """Create a real account and log it in. Returns the user and the raw session token."""
    normalized = validate_credentials(username, password)
    if db.scalar(select(User.id).where(User.username == normalized)) is not None:
        raise UsernameTaken(normalized)

    account = Account(
        kind=AccountKind.user,
        display_name=(display_name or normalized).strip() or normalized,
    )
    db.add(account)
    db.flush()
    user = User(
        account_id=account.id,
        username=normalized,
        password_hash=hash_password(password),
    )
    db.add(user)
    try:
        db.flush()
    except IntegrityError as exc:  # lost a race against a concurrent signup
        db.rollback()
        raise UsernameTaken(normalized) from exc

    token = _open_session(db, account.id)
    db.commit()
    return user, token


def login(db: Session, *, username: str, password: str) -> tuple[User, str]:
    normalized = normalize_username(username)
    user = db.scalar(select(User).where(User.username == normalized))
    if user is None:
        verify_password(DUMMY_HASH, password)
        raise InvalidCredentials
    if not verify_password(user.password_hash, password):
        raise InvalidCredentials

    token = _open_session(db, user.account_id)
    db.commit()
    return user, token


def logout(db: Session, token: str | None) -> None:
    """Revoke the session. Idempotent: an unknown or missing token is not an error."""
    if not token:
        return
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_digest(token)))
    if session is not None:
        db.delete(session)
        db.commit()


def user_for_token(db: Session, token: str | None) -> User:
    if not token:
        raise InvalidSession
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_digest(token)))
    if session is None:
        raise InvalidSession
    if session.expires_at <= utcnow_naive():
        db.delete(session)
        db.commit()
        raise InvalidSession
    user = db.scalar(select(User).where(User.account_id == session.account_id))
    if user is None:
        raise InvalidSession
    return user


def account_for(db: Session, account_id: int) -> Account:
    account = db.get(Account, account_id)
    if account is None:  # pragma: no cover - accounts are never deleted
        raise InvalidSession
    return account


def _open_session(db: Session, account_id: int) -> str:
    token = new_session_token()
    db.add(
        AuthSession(
            account_id=account_id,
            token_hash=token_digest(token),
            expires_at=utcnow_naive() + timedelta(days=settings.session_ttl_days),
        )
    )
    return token
