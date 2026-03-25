from __future__ import annotations

from decimal import Decimal

from app.agents.types import RouteCandidate
from app.providers.registry import ProviderRegistry


def _compute_cost_score(*, fee_total: Decimal, eta_seconds: int, speed_preference: str) -> Decimal:
    if speed_preference == "cheapest":
        return fee_total
    if speed_preference == "fastest":
        return Decimal(eta_seconds)
    # balanced
    return fee_total + (Decimal(eta_seconds) / Decimal(1000))


async def route_optimizer_node(state: dict) -> dict:
    request = state["request"]
    provider_registry: ProviderRegistry = state["provider_registry"]
    corridors = state["corridors"]

    speed_preference = request.speed_preference
    candidates: list[RouteCandidate] = []

    for corridor in corridors:
        for rail_type in corridor.available_rails:
            quote = await provider_registry.quote_route(
                request=request, corridor=corridor, rail_type=rail_type
            )
            if quote is None:
                continue

            cost_score = _compute_cost_score(
                fee_total=quote.fee_total,
                eta_seconds=quote.eta_seconds,
                speed_preference=speed_preference,
            )
            confidence = float(quote.liquidity_confidence) * 0.7 + 0.3

            candidates.append(
                RouteCandidate(
                    corridor_key=quote.corridor_key,
                    rail_type=quote.rail_type,
                    fee_total=quote.fee_total,
                    eta_seconds=quote.eta_seconds,
                    liquidity_confidence=quote.liquidity_confidence,
                    payout_currency=quote.payout_currency,
                    provider_path=quote.provider_path,
                    cost_score=cost_score,
                    confidence=confidence,
                    fx_rate=None,
                    fx_spread=None,
                    all_in_total=None,
                )
            )

    if not candidates:
        # Upstream failure: no quotes available for the selected corridor/rails.
        raise RuntimeError("No route candidates available from provider registry")

    # Initial best route selection before FX enrichment.
    candidates.sort(key=lambda c: (c.cost_score if c.cost_score is not None else Decimal("1e18")))
    recommended = candidates[0]
    return {"route_candidates": candidates, "recommended_route": recommended}

