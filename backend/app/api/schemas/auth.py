from pydantic import BaseModel, Field, model_validator

CURRENCY_PATTERN = r"^[a-zA-Z]{3}$"


class SignupRequest(BaseModel):
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    password: str = Field(min_length=8, max_length=128)
    default_currency: str = Field(min_length=3, max_length=3, pattern=CURRENCY_PATTERN)
    display_name: str | None = Field(default=None, min_length=1, max_length=100)


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class UpdateMeRequest(BaseModel):
    default_currency: str | None = Field(
        default=None, min_length=3, max_length=3, pattern=CURRENCY_PATTERN
    )
    display_name: str | None = Field(default=None, min_length=1, max_length=100)

    @model_validator(mode="after")
    def at_least_one_field(self) -> "UpdateMeRequest":
        if self.default_currency is None and self.display_name is None:
            raise ValueError("provide default_currency or display_name")
        return self


class MeResponse(BaseModel):
    account_id: int
    username: str
    display_name: str
    default_currency: str
