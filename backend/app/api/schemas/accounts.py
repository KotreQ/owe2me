from pydantic import BaseModel, Field


class AccountResponse(BaseModel):
    id: int
    kind: str
    display_name: str
    username: str | None = None
    owner_account_id: int | None = None


class CreateLocalAccountRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


class LinkLocalAccountRequest(BaseModel):
    target_username: str = Field(min_length=1, max_length=50)


class LinkLocalAccountResponse(BaseModel):
    account: AccountResponse
    rewritten_entries: int
