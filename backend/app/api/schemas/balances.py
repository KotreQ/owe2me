from pydantic import BaseModel

from app.models import AccountKind


class BalanceResponse(BaseModel):
    account_id: int
    display_name: str
    kind: AccountKind
    currency: str
    net_minor: int
