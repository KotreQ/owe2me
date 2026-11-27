from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.entries import (
    CreateEntryRequest,
    EntryPageResponse,
    EntryResponse,
)
from app.db.session import get_db
from app.models import Account, Entry, EntryStatus, User
from app.services import entries as entries_service
from app.services.entries import (
    EntryConflict,
    EntryError,
    EntryForbidden,
    EntryInvalid,
    EntryNotFound,
)

router = APIRouter(prefix="/entries", tags=["entries"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]

DEFAULT_LIMIT = 50
MAX_LIMIT = 200


def _names(db: Session, entries: list[Entry]) -> dict[int, str]:
    ids = {entry.payer_account_id for entry in entries}
    ids.update(entry.payee_account_id for entry in entries)
    if not ids:
        return {}
    return {
        account_id: display_name
        for account_id, display_name in db.execute(
            select(Account.id, Account.display_name).where(Account.id.in_(ids))
        )
    }


def _entry_response(
    db: Session, entry: Entry, names: dict[int, str] | None = None
) -> EntryResponse:
    names = names if names is not None else _names(db, [entry])
    return EntryResponse(
        id=entry.id,
        payer_account_id=entry.payer_account_id,
        payer_display_name=names.get(entry.payer_account_id, ""),
        payee_account_id=entry.payee_account_id,
        payee_display_name=names.get(entry.payee_account_id, ""),
        kind=entry.kind,
        amount_minor=entry.amount_minor,
        currency=entry.currency,
        title=entry.title,
        status=entry.status,
        provisional=entry.provisional,
        created_by_account_id=entry.created_by_account_id,
        decided_by_account_id=entry.decided_by_account_id,
        decided_at=entry.decided_at,
        created_at=entry.created_at,
    )


def _page(
    db: Session, page: entries_service.EntryPage, limit: int, offset: int
) -> EntryPageResponse:
    names = _names(db, page.items)
    return EntryPageResponse(
        items=[_entry_response(db, entry, names) for entry in page.items],
        total=page.total,
        limit=limit,
        offset=offset,
    )


def _handle_error(exc: EntryError) -> HTTPException:
    if isinstance(exc, EntryNotFound):
        return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, EntryForbidden):
        return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    if isinstance(exc, EntryConflict):
        return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    if isinstance(exc, EntryInvalid):
        return HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc))
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))


@router.post("", status_code=status.HTTP_201_CREATED, response_model=EntryResponse)
def create_entry(body: CreateEntryRequest, user: CurrentUser, db: DbSession) -> EntryResponse:
    try:
        entry = entries_service.create_entry(
            db,
            actor_account_id=user.account_id,
            payer_account_id=body.payer_account_id,
            payee_account_id=body.payee_account_id,
            kind=body.kind,
            amount_minor=body.amount_minor,
            currency=body.currency,
            title=body.title,
        )
    except EntryError as exc:
        raise _handle_error(exc) from exc
    return _entry_response(db, entry)


@router.get("", response_model=EntryPageResponse)
def list_entries(
    user: CurrentUser,
    db: DbSession,
    with_account_id: Annotated[int | None, Query(alias="with")] = None,
    status_filter: Annotated[EntryStatus | None, Query(alias="status")] = None,
    currency: Annotated[str | None, Query(min_length=3, max_length=3)] = None,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EntryPageResponse:
    page = entries_service.list_entries(
        db,
        account_id=user.account_id,
        with_account_id=with_account_id,
        status=status_filter,
        currency=currency,
        limit=limit,
        offset=offset,
    )
    return _page(db, page, limit, offset)


@router.get("/pending", response_model=EntryPageResponse)
def pending_entries(
    user: CurrentUser,
    db: DbSession,
    limit: Annotated[int, Query(ge=1, le=MAX_LIMIT)] = DEFAULT_LIMIT,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> EntryPageResponse:
    page = entries_service.list_entries(
        db,
        account_id=user.account_id,
        status=EntryStatus.pending,
        exclude_created_by_me=True,
        limit=limit,
        offset=offset,
    )
    return _page(db, page, limit, offset)


@router.get("/{entry_id}", response_model=EntryResponse)
def get_entry(entry_id: int, user: CurrentUser, db: DbSession) -> EntryResponse:
    try:
        entry = entries_service.visible_entry(
            db, entry_id=entry_id, viewer_account_id=user.account_id
        )
    except EntryNotFound as exc:
        raise _handle_error(exc) from exc
    return _entry_response(db, entry)


@router.post("/{entry_id}/accept", response_model=EntryResponse)
def accept_entry(entry_id: int, user: CurrentUser, db: DbSession) -> EntryResponse:
    return _decide(db, entry_id, user, accept=True)


@router.post("/{entry_id}/reject", response_model=EntryResponse)
def reject_entry(entry_id: int, user: CurrentUser, db: DbSession) -> EntryResponse:
    return _decide(db, entry_id, user, accept=False)


@router.post("/{entry_id}/cancel", status_code=status.HTTP_204_NO_CONTENT)
def cancel_entry(entry_id: int, user: CurrentUser, db: DbSession) -> Response:
    try:
        entries_service.cancel_entry(db, actor_account_id=user.account_id, entry_id=entry_id)
    except EntryError as exc:
        raise _handle_error(exc) from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _decide(db: Session, entry_id: int, user: User, *, accept: bool) -> EntryResponse:
    try:
        entry = entries_service.decide_entry(
            db,
            actor_account_id=user.account_id,
            entry_id=entry_id,
            accept=accept,
        )
    except EntryError as exc:
        raise _handle_error(exc) from exc
    return _entry_response(db, entry)
