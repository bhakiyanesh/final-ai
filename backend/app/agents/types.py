from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from app.models.transfer import QuoteRequest


RailType = Literal["stablecoin", "ach", "mobile_money"]
SpeedPreference = Literal["fastest", "balanced", "cheapest"]
DeliveryMethod = Literal["bank", "mobile", "cash", "stablecoin"]


class CorridorCandidate(BaseModel):
    corridor_key: str
    available_rails: list[RailType]
    confidence: float = Field(ge=0.0, le=1.0)
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class RouteQuote(BaseModel):
    corridor_key: str
    rail_type: RailType

    # Provider-determined outputs
    fee_total: Decimal = Field(ge=0)
    eta_seconds: int = Field(ge=0)
    liquidity_confidence: float = Field(ge=0.0, le=1.0)
    payout_currency: str = Field(min_length=3, max_length=3)
    provider_path: list[str] = Field(default_factory=list)

    # Metadata for transparency/audit
    provider_metadata: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")


class RouteCandidate(BaseModel):
    corridor_key: str
    rail_type: RailType

    fee_total: Decimal = Field(ge=0)
    eta_seconds: int = Field(ge=0)
    liquidity_confidence: float = Field(ge=0.0, le=1.0)
    payout_currency: str = Field(min_length=3, max_length=3)
    provider_path: list[str] = Field(default_factory=list)

    # Scoring
    cost_score: Decimal | None = None
    confidence: float = Field(ge=0.0, le=1.0)

    # FX enrichment (added by FX agent)
    fx_rate: Decimal | None = None
    fx_spread: Decimal | None = None
    all_in_total: Decimal | None = None  # in sender currency

    model_config = ConfigDict(extra="forbid")


class PricingQuoteResponse(BaseModel):
    request: QuoteRequest

    recommended_route: RouteCandidate
    route_alternatives: list[RouteCandidate]

    total_fee: Decimal
    fx_rate_snapshot: Decimal | None
    fx_spread: Decimal | None
    delivery_eta_seconds: int
    delivery_method: DeliveryMethod
    all_in_total: Decimal

    ai_explanation: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)

    model_config = ConfigDict(extra="forbid")


class GraphError(BaseModel):
    step: str
    message: str
    details: dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(extra="forbid")

