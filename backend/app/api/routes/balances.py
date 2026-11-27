from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.balances import BalanceResponse, BalanceTotalsResponse
from app.db.session import get_db
from app.models import User
from app.services.accounts import AccountNotFound, visible_account
from app.services.entries import Balance, balance_totals, balances_for

router = APIRouter(prefix="/balances", tags=["balances"])

DbSession = Annotated[Session, Depends(get_db)]
CurrentUser = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=list[BalanceResponse])
def list_balances(
    user: CurrentUser,
    db: DbSession,
    include_zero: Annotated[bool, Query()] = False,
) -> list[BalanceResponse]:
    """Net position per counterparty and currency; positive means they owe me."""
    return [
        _response(balance)
        for balance in balances_for(db, user.account_id, include_zero=include_zero)
    ]


@router.get("/totals", response_model=list[BalanceTotalsResponse])
def totals(
    user: CurrentUser,
    db: DbSession,
) -> list[BalanceTotalsResponse]:
    """Sum per currency across every counterparty; no conversion between currencies."""
    return [
        BalanceTotalsResponse(
            currency=total.currency,
            owed_by_others_minor=total.owed_by_others_minor,
            owed_to_others_minor=total.owed_to_others_minor,
            net_minor=total.net_minor,
        )
        for total in balance_totals(db, user.account_id)
    ]


@router.get("/{account_id}", response_model=list[BalanceResponse])
def balance_with(
    account_id: int,
    user: CurrentUser,
    db: DbSession,
    include_zero: Annotated[bool, Query()] = False,
) -> list[BalanceResponse]:
    """Balances with one counterparty, one row per currency."""
    try:
        visible_account(db, account_id=account_id, viewer_account_id=user.account_id)
    except AccountNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="account not found"
        ) from exc

    return [
        _response(balance)
        for balance in balances_for(db, user.account_id, include_zero=include_zero)
        if balance.other_account_id == account_id
    ]


def _response(balance: Balance) -> BalanceResponse:
    return BalanceResponse(
        account_id=balance.other_account_id,
        display_name=balance.display_name,
        kind=balance.kind,
        currency=balance.currency,
        net_minor=balance.net_minor,
    )
