from __future__ import annotations

from app.agents.types import CorridorCandidate
from app.providers.registry import ProviderRegistry


async def corridor_analysis_node(state: dict) -> dict:
    request = state["request"]
    provider_registry: ProviderRegistry = state["provider_registry"]

    available_rails = provider_registry.get_viable_rails(request)
    corridor_key = f"{request.sender_country}->{request.receiver_country}"

    confidence = 0.9 if available_rails else 0.2
    corridor = CorridorCandidate(
        corridor_key=corridor_key,
        available_rails=available_rails,
        confidence=confidence,
        details={
            "corridor_key": corridor_key,
            "rails_source": "provider_registry.get_viable_rails",
        },
    )

    return {"corridors": [corridor]}

