from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.schemas.balances import BalanceResponse
from app.db.session import get_db
from app.models import User
from app.services.entries import balances_for

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
        BalanceResponse(
            account_id=balance.other_account_id,
            display_name=balance.display_name,
            kind=balance.kind,
            currency=balance.currency,
            net_minor=balance.net_minor,
        )
        for balance in balances_for(db, user.account_id, include_zero=include_zero)
    ]
