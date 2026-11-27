from pydantic import BaseModel, Field


class AccountResponse(BaseModel):
    account_id: int
    kind: str
    display_name: str
    username: str | None = None


class UserLookupResponse(BaseModel):
    account_id: int
    display_name: str
    username: str


class CreateLocalAccountRequest(BaseModel):
    display_name: str = Field(min_length=1, max_length=100)


class LinkLocalAccountRequest(BaseModel):
    target_username: str = Field(min_length=1, max_length=50)


class LinkLocalAccountResponse(BaseModel):
    account: AccountResponse
    rewritten_entries: int
