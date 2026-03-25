from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


SpeedPreference = Literal["fastest", "balanced", "cheapest"]
PayoutPreference = Literal["bank", "mobile", "cash", "stablecoin"]


class QuoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sender_country: str = Field(min_length=2, max_length=2)
    receiver_country: str = Field(min_length=2, max_length=2)
    amount: Decimal
    currency: str = Field(min_length=3, max_length=3)
    speed_preference: SpeedPreference
    payout_preference: PayoutPreference

    recipient_identifier: str | None = None

    @field_validator("sender_country", "receiver_country", mode="before")
    @classmethod
    def normalize_country_code(cls, v: str) -> str:
        if not isinstance(v, str):
            raise TypeError("Country code must be a string")
        v = v.strip().upper()
        if len(v) != 2:
            raise ValueError("Country code must be 2 characters")
        if not v.isalpha():
            raise ValueError("Country code must be alphabetic")
        return v

    @field_validator("currency", mode="before")
    @classmethod
    def normalize_currency_code(cls, v: str) -> str:
        if not isinstance(v, str):
            raise TypeError("Currency code must be a string")
        v = v.strip().upper()
        if len(v) != 3:
            raise ValueError("Currency code must be 3 characters")
        if not v.isalpha():
            raise ValueError("Currency code must be alphabetic")
        return v

    @field_validator("amount")
    @classmethod
    def validate_amount_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("amount must be > 0")
        return v


class CreateTransferRequest(QuoteRequest):
    idempotency_key: str

