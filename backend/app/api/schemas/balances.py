from pydantic import BaseModel

from app.models import AccountKind


class BalanceResponse(BaseModel):
    account_id: int
    display_name: str
    kind: AccountKind
    currency: str
    net_minor: int


class BalanceTotalsResponse(BaseModel):
    currency: str
    owed_by_others_minor: int
    owed_to_others_minor: int
    net_minor: int
