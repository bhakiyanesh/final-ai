from __future__ import annotations

from decimal import Decimal
from typing import Any

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.agents.types import RailType
from app.models.transfer import QuoteRequest
from app.providers.types import (
    ProviderExecutionResult,
    ProviderQuoteResultBase,
    ProviderStatusResult,
)


class HttpQuoteResponseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fee_total: Decimal
    eta_seconds: int
    liquidity_confidence: float = Field(ge=0.0, le=1.0)
    payout_currency: str = Field(min_length=3, max_length=3)
    provider_path: list[str] = Field(default_factory=list)
    provider_metadata: dict[str, Any] = Field(default_factory=dict)


class HttpProviderAdapter:
    """
    Generic HTTP-based rail adapter.

    Provider contracts (expected request/response shapes) are standardized to
    `ProviderQuoteResultBase`, `ProviderExecutionResult`, and `ProviderStatusResult`.
    """

    def __init__(
        self,
        *,
        rail_type: RailType,
        quote_url: str,
        execute_url: str | None = None,
        status_url: str | None = None,
        timeout_s: int = 12,
    ) -> None:
        self.rail_type = rail_type
        self.quote_url = quote_url
        self.execute_url = execute_url
        self.status_url = status_url
        self.timeout_s = timeout_s

    async def quote_route(
        self,
        *,
        request: QuoteRequest,
        corridor_key: str,
    ) -> ProviderQuoteResultBase:
        payload = {
            "rail_type": self.rail_type,
            "corridor_key": corridor_key,
            "sender_country": request.sender_country,
            "receiver_country": request.receiver_country,
            "amount": str(request.amount),
            "currency": request.currency,
            "speed_preference": request.speed_preference,
            "payout_preference": request.payout_preference,
            "recipient_identifier": request.recipient_identifier,
        }

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            res = await client.post(self.quote_url, json=payload)
            res.raise_for_status()
            body = res.json()

        parsed = HttpQuoteResponseModel.model_validate(body)
        return ProviderQuoteResultBase(
            fee_total=parsed.fee_total,
            eta_seconds=parsed.eta_seconds,
            liquidity_confidence=parsed.liquidity_confidence,
            payout_currency=parsed.payout_currency,
            provider_path=parsed.provider_path,
            provider_metadata=parsed.provider_metadata,
        )

    async def execute(self, *, execute_payload: dict[str, Any]) -> ProviderExecutionResult:
        if not self.execute_url:
            raise RuntimeError(f"No execute_url configured for rail {self.rail_type}")

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            res = await client.post(self.execute_url, json=execute_payload)
            res.raise_for_status()
            body = res.json()

        return ProviderExecutionResult.model_validate(body)

    async def status(self, *, provider_reference: str) -> ProviderStatusResult:
        if not self.status_url:
            raise RuntimeError(f"No status_url configured for rail {self.rail_type}")

        async with httpx.AsyncClient(timeout=self.timeout_s) as client:
            res = await client.get(self.status_url, params={"provider_reference": provider_reference})
            res.raise_for_status()
            body = res.json()

        return ProviderStatusResult.model_validate(body)

