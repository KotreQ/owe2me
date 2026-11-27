from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models import User
from app.services.auth import InvalidSession, user_for_token

settings = get_settings()


def get_current_user(
    db: Annotated[Session, Depends(get_db)],
    session_token: Annotated[str | None, Cookie(alias=settings.session_cookie_name)] = None,
) -> User:
    try:
        return user_for_token(db, session_token)
    except InvalidSession as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="not authenticated",
            headers={"WWW-Authenticate": "Session"},
        ) from exc


CurrentUser = Annotated[User, Depends(get_current_user)]
