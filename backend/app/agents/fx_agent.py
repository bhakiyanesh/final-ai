from __future__ import annotations

from decimal import Decimal

from app.agents.fx_service import best_fx_rate


def _select_by_speed(route: dict, speed_preference: str) -> Decimal | int:
    # Helper for stable sorting keys.
    if speed_preference == "fastest":
        return route["eta_seconds"]
    if speed_preference == "cheapest":
        return route["all_in_total"]
    return route["all_in_total"] + (Decimal(route["eta_seconds"]) / Decimal(1000))


async def fx_agent_node(state: dict) -> dict:
    request = state["request"]
    candidates = state["route_candidates"]
    speed_preference = request.speed_preference

    base_currency = request.currency

    fx_rate_snapshot = None
    fx_spread_snapshot = None
    fx_confidence = 0.0

    enriched = []
    for c in candidates:
        try:
            fx = await best_fx_rate(base_currency, c.payout_currency)
            fx_rate = fx.best_rate
            fx_spread = fx.spread_fraction
            all_in_total = request.amount + c.fee_total + (request.amount * fx_spread)

            confidence = float(c.confidence) * 0.6 + fx.confidence * 0.4
            enriched.append(
                c.model_copy(
                    update={
                        "fx_rate": fx_rate,
                        "fx_spread": fx_spread,
                        "all_in_total": all_in_total,
                        "confidence": confidence,
                    }
                )
            )

            fx_rate_snapshot = fx_rate_snapshot or fx_rate
            fx_spread_snapshot = fx_spread_snapshot or fx_spread
            fx_confidence = max(fx_confidence, fx.confidence)
        except Exception:
            # Fallback if FX sources are unreachable.
            # Note: this degrades accuracy by assuming a 1:1 conversion for pricing.
            fx_rate = Decimal("1")
            fx_spread = Decimal("0")
            all_in_total = request.amount + c.fee_total

            enriched.append(
                c.model_copy(
                    update={
                        "fx_rate": fx_rate,
                        "fx_spread": fx_spread,
                        "all_in_total": all_in_total,
                        "confidence": float(c.confidence) * 0.5,
                    }
                )
            )

    if not enriched:
        raise RuntimeError("FX enrichment failed for all candidates")

    def sort_key(rc):
        assert rc.all_in_total is not None
        return _select_by_speed(
            {
                "eta_seconds": rc.eta_seconds,
                "all_in_total": rc.all_in_total,
            },
            speed_preference,
        )

    enriched.sort(key=sort_key)
    recommended = enriched[0]

    return {
        "route_candidates": enriched,
        "recommended_route": recommended,
        "fx_rate_snapshot": recommended.fx_rate,
        "fx_spread": recommended.fx_spread,
        "fx_confidence": fx_confidence,
    }

