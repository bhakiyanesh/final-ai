from __future__ import annotations

from app.agents.types import PricingQuoteResponse
from app.core.config import settings
from app.llm.explain import generate_route_explanation


def _delivery_method_from_preference(payout_preference: str) -> str:
    if payout_preference == "stablecoin":
        return "stablecoin"
    if payout_preference == "bank":
        return "bank"
    if payout_preference == "mobile":
        return "mobile"
    if payout_preference == "cash":
        return "cash"
    return "bank"


async def last_mile_node(state: dict) -> dict:
    request = state["request"]
    corridors = state["corridors"]
    candidates = state["route_candidates"]
    recommended = state["recommended_route"]

    fx_rate_snapshot = state.get("fx_rate_snapshot")
    fx_spread_snapshot = state.get("fx_spread")
    fx_confidence = state.get("fx_confidence", 0.0)

    # Keep only a handful of alternatives for UI readability.
    candidates_sorted = list(candidates)
    candidates_sorted = sorted(candidates_sorted, key=lambda c: (c.all_in_total or 0))
    route_alternatives = candidates_sorted[:3]

    corridor_confidence = corridors[0].confidence if corridors else 0.0
    delivery_eta_seconds = int(recommended.eta_seconds)

    delivery_method = _delivery_method_from_preference(request.payout_preference)

    total_fee = recommended.fee_total
    all_in_total = recommended.all_in_total
    if all_in_total is None:
        raise RuntimeError("Missing all_in_total after FX enrichment")

    overall_confidence = float(recommended.confidence) * 0.6 + corridor_confidence * 0.2 + fx_confidence * 0.2

    response = PricingQuoteResponse(
        request=request,
        recommended_route=recommended,
        route_alternatives=route_alternatives,
        total_fee=total_fee,
        fx_rate_snapshot=fx_rate_snapshot,
        fx_spread=fx_spread_snapshot,
        delivery_eta_seconds=delivery_eta_seconds,
        delivery_method=delivery_method,
        all_in_total=all_in_total,
        ai_explanation=None,
        confidence=min(1.0, max(0.0, overall_confidence)),
    )

    # Optional LLM-powered "Why this route?" explanation.
    # If no LLM is configured, we keep ai_explanation omitted.
    llm_configured = bool(settings.llm_openrouter_api_key) or bool(settings.llm_ollama_model)
    if llm_configured:
        try:
            request_context = {
                "sender_country": request.sender_country,
                "receiver_country": request.receiver_country,
                "amount": str(request.amount),
                "currency": request.currency,
                "speed_preference": request.speed_preference,
                "payout_preference": request.payout_preference,
            }

            explanation, confidence_adjustment = await generate_route_explanation(
                request_context=request_context,
                recommended=recommended,
                alternatives=route_alternatives,
            )

            response = response.model_copy(
                update={
                    "ai_explanation": explanation,
                    "confidence": min(
                        1.0, max(0.0, float(response.confidence) + confidence_adjustment)
                    ),
                }
            )
        except Exception:
            # Explanation is non-critical; pricing remains deterministic.
            pass

    return {"pricing_response": response}

