from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


ProviderStatus = Literal["created", "executing", "sent", "failed", "cancelled"]


class ProviderExecutionResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_reference: str
    status: ProviderStatus
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderStatusResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_reference: str
    status: ProviderStatus
    eta_seconds: int | None = None
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class ProviderQuoteResultBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fee_total: Decimal
    eta_seconds: int
    liquidity_confidence: float
    payout_currency: str
    provider_path: list[str] = Field(default_factory=list)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)

