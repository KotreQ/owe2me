from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.api.deps import CurrentUser
from app.api.schemas.auth import LoginRequest, MeResponse, SignupRequest
from app.core.config import get_settings
from app.db.session import get_db
from app.models import User
from app.services import auth
from app.services.auth import AuthError, InvalidCredentials, UsernameTaken

router = APIRouter(prefix="/auth", tags=["auth"])
settings = get_settings()

DbSession = Annotated[Session, Depends(get_db)]


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_days * 24 * 60 * 60,
        httponly=True,
        secure=settings.session_cookie_secure,
        samesite=settings.session_cookie_samesite,
        path="/",
    )


def _me(db: Session, user: User) -> MeResponse:
    account = auth.account_for(db, user.account_id)
    return MeResponse(
        account_id=account.id,
        username=user.username,
        display_name=account.display_name,
    )


@router.post("/signup", status_code=status.HTTP_201_CREATED, response_model=MeResponse)
def signup(body: SignupRequest, response: Response, db: DbSession) -> MeResponse:
    try:
        user, token = auth.signup(
            db,
            username=body.username,
            password=body.password,
            display_name=body.display_name,
        )
    except UsernameTaken as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="username already taken"
        ) from exc
    except AuthError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
        ) from exc

    _set_session_cookie(response, token)
    return _me(db, user)


@router.post("/login", response_model=MeResponse)
def login(body: LoginRequest, response: Response, db: DbSession) -> MeResponse:
    try:
        user, token = auth.login(db, username=body.username, password=body.password)
    except InvalidCredentials as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid username or password"
        ) from exc

    _set_session_cookie(response, token)
    return _me(db, user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    db: DbSession,
    session_token: Annotated[str | None, Cookie(alias=settings.session_cookie_name)] = None,
) -> Response:
    auth.logout(db, session_token)
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    response.delete_cookie(key=settings.session_cookie_name, path="/")
    return response


@router.get("/me", response_model=MeResponse)
def me(user: CurrentUser, db: DbSession) -> MeResponse:
    return _me(db, user)
