from __future__ import annotations

import json
import re
from decimal import Decimal
from typing import Any

from langsmith import traceable
from pydantic import BaseModel, ConfigDict, Field

from app.agents.types import PricingQuoteResponse, RouteCandidate
from app.llm.llm_client import chat_completion_with_fallback


class RouteExplanationOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    why_route: str = Field(min_length=10, max_length=2000)
    tradeoff_summary: str = Field(min_length=5, max_length=1000)
    confidence_adjustment: float = Field(ge=-0.25, le=0.25)


def _extract_json_object(text: str) -> dict[str, Any]:
    # Robust extraction in case the model includes leading/trailing text.
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("No JSON object found in LLM output")
    candidate = text[start : end + 1]
    return json.loads(candidate)


@traceable(run_type="llm", name="route_explanation")
async def generate_route_explanation(
    *,
    request_context: dict[str, Any],
    recommended: RouteCandidate,
    alternatives: list[RouteCandidate],
) -> tuple[str, float]:
    """
    Generates a human-friendly "Why this route?" explanation and a confidence adjustment.
    """
    payload = {
        "request": request_context,
        "recommended_route": recommended.model_dump(mode="json"),
        "route_alternatives": [a.model_dump(mode="json") for a in alternatives],
    }

    messages = [
        {
            "role": "system",
            "content": (
                "You are a fintech remittance optimization expert. "
                "Explain why the recommended route is best, considering cost (fees + FX spread) "
                "and speed tradeoffs. Output ONLY a JSON object with the required schema."
            ),
        },
        {
            "role": "user",
            "content": (
                "Given the following pricing and route candidates, generate a brief explanation. "
                "If you cannot confidently infer a detail, say so explicitly. \n\n"
                "Return JSON with keys: why_route, tradeoff_summary, confidence_adjustment.\n\n"
                f"INPUT_JSON={json.dumps(payload)}"
            ),
        },
    ]

    model_text = await chat_completion_with_fallback(messages)
    data = _extract_json_object(model_text)
    parsed = RouteExplanationOutput.model_validate(data)

    explanation = (
        f"{parsed.why_route}\n\nTradeoff: {parsed.tradeoff_summary}"
    )
    return explanation, float(parsed.confidence_adjustment)

