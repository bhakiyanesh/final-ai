from __future__ import annotations

from decimal import Decimal
from typing import List, NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from app.agents.corridor_agent import corridor_analysis_node
from app.agents.fx_agent import fx_agent_node
from app.agents.last_mile_agent import last_mile_node
from app.agents.route_optimizer_agent import route_optimizer_node
from app.agents.types import CorridorCandidate, PricingQuoteResponse, RouteCandidate
from app.models.transfer import QuoteRequest as InputQuoteRequest
from app.providers.registry import ProviderRegistry


class QuoteGraphState(TypedDict):
    request: InputQuoteRequest
    provider_registry: ProviderRegistry

    corridors: NotRequired[List[CorridorCandidate]]
    route_candidates: NotRequired[List[RouteCandidate]]
    recommended_route: NotRequired[RouteCandidate]

    fx_rate_snapshot: NotRequired[Decimal | None]
    fx_spread: NotRequired[Decimal | None]
    fx_confidence: NotRequired[float]

    pricing_response: NotRequired[PricingQuoteResponse]


def build_quote_graph():
    builder = StateGraph(QuoteGraphState)
    builder.add_node("corridor_analysis", corridor_analysis_node)
    builder.add_node("route_optimizer", route_optimizer_node)
    builder.add_node("fx_agent", fx_agent_node)
    builder.add_node("last_mile", last_mile_node)

    builder.add_edge(START, "corridor_analysis")
    builder.add_edge("corridor_analysis", "route_optimizer")
    builder.add_edge("route_optimizer", "fx_agent")
    builder.add_edge("fx_agent", "last_mile")
    builder.add_edge("last_mile", END)

    return builder.compile()


quote_graph = build_quote_graph()


async def run_pricing_quote(request: InputQuoteRequest) -> PricingQuoteResponse:
    provider_registry = ProviderRegistry()
    initial_state: QuoteGraphState = {
        "request": request,
        "provider_registry": provider_registry,
    }

    final_state = await quote_graph.ainvoke(initial_state)
    pricing_response = final_state.get("pricing_response")
    if pricing_response is None:
        raise RuntimeError("Graph did not return pricing_response")
    return pricing_response

