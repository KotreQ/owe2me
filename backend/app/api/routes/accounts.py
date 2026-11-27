from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.accounts import (
    AccountResponse,
    CreateLocalAccountRequest,
    LinkLocalAccountRequest,
    LinkLocalAccountResponse,
    UserLookupResponse,
)
from app.db.session import get_db
from app.models import Account, User
from app.services import accounts as accounts_service
from app.services import auth
from app.services.accounts import AccountConflict, AccountError, AccountNotFound

router = APIRouter(prefix="/accounts", tags=["accounts"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


def _response(db: Session, account: Account) -> AccountResponse:
    username = None
    if account.kind.value == "user":
        username = db.scalar(select(User.username).where(User.account_id == account.id))
    return AccountResponse(
        account_id=account.id,
        kind=account.kind.value,
        display_name=account.display_name,
        username=username,
    )


def _not_found() -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="account not found")


@router.post("/local", status_code=status.HTTP_201_CREATED, response_model=AccountResponse)
def create_local_account(
    body: CreateLocalAccountRequest, user: CurrentUser, db: DbSession
) -> AccountResponse:
    try:
        account = accounts_service.create_local_account(
            db, owner_account_id=user.account_id, display_name=body.display_name
        )
    except AccountConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    except AccountError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    return _response(db, account)


@router.get("", response_model=list[AccountResponse])
def list_contacts(user: CurrentUser, db: DbSession) -> list[AccountResponse]:
    return [
        _response(db, account)
        for account in accounts_service.list_contacts(db, account_id=user.account_id)
    ]


@router.get("/lookup", response_model=UserLookupResponse)
def lookup_user(
    user: CurrentUser,
    db: DbSession,
    username: Annotated[str, Query(min_length=1, max_length=50)],
) -> UserLookupResponse:
    """Resolve an exact login name to an account id so a real user can be added."""
    found = accounts_service.find_user_by_username(db, username)
    if found is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    account = db.get(Account, found.account_id)
    if account is None:  # pragma: no cover - users always have an account
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return UserLookupResponse(
        account_id=account.id,
        display_name=account.display_name,
        username=found.username,
    )


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(account_id: int, user: CurrentUser, db: DbSession) -> AccountResponse:
    try:
        account = accounts_service.visible_account(
            db, account_id=account_id, viewer_account_id=user.account_id
        )
    except AccountNotFound as exc:
        raise _not_found() from exc
    return _response(db, account)


@router.post("/{account_id}/link", response_model=LinkLocalAccountResponse)
def link_local_account(
    account_id: int, body: LinkLocalAccountRequest, user: CurrentUser, db: DbSession
) -> LinkLocalAccountResponse:
    target_username = auth.normalize_username(body.target_username)
    target = db.scalar(
        select(User).where(User.username == target_username, User.account_id != user.account_id)
    )
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="target user not found")

    try:
        rewritten = accounts_service.link_local_account(
            db,
            actor_account_id=user.account_id,
            alias_account_id=account_id,
            target_account_id=target.account_id,
        )
    except AccountNotFound as exc:
        raise _not_found() from exc
    except AccountConflict as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    target_account = db.get(Account, target.account_id)
    return LinkLocalAccountResponse(
        account=_response(db, target_account), rewritten_entries=rewritten
    )
