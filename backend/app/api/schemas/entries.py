from datetime import datetime

from pydantic import BaseModel, Field

from app.models import EntryKind, EntryStatus


class CreateEntryRequest(BaseModel):
    payer_account_id: int
    payee_account_id: int
    kind: EntryKind
    amount_minor: int = Field(gt=0)
    currency: str = Field(min_length=3, max_length=3, pattern=r"^[a-zA-Z]{3}$")
    title: str = Field(min_length=1, max_length=120)


class EntryResponse(BaseModel):
    id: int
    payer_account_id: int
    payer_display_name: str
    payee_account_id: int
    payee_display_name: str
    kind: EntryKind
    amount_minor: int
    currency: str
    title: str
    status: EntryStatus
    provisional: bool
    created_by_account_id: int
    decided_by_account_id: int | None
    decided_at: datetime | None
    created_at: datetime


class EntryPageResponse(BaseModel):
    items: list[EntryResponse]
    total: int
    limit: int
    offset: int
