import os
from decimal import Decimal

import pytest

from app.agents.types import CorridorCandidate
from app.models.transfer import QuoteRequest
from app.providers.registry import ProviderRegistry


@pytest.mark.asyncio
async def test_provider_registry_mock_quote_and_execute(monkeypatch):
    monkeypatch.setenv("ENABLE_MOCK_RAILS", "true")

    reg = ProviderRegistry()
    req = QuoteRequest(
        sender_country="US",
        receiver_country="NG",
        amount=Decimal("250"),
        currency="USD",
        speed_preference="cheapest",
        payout_preference="bank",
        recipient_identifier=None,
    )
    corridor = CorridorCandidate(corridor_key="US->NG", available_rails=["ach"], confidence=1.0)

    quote = await reg.quote_route(request=req, corridor=corridor, rail_type="ach")
    assert quote is not None
    assert quote.rail_type == "ach"
    assert quote.eta_seconds > 0

    exec_result = await reg.execute_transfer(rail_type="ach", execute_payload={"foo": "bar"})
    assert exec_result.status == "sent"

    status = await reg.get_provider_status(rail_type="ach", provider_reference=exec_result.provider_reference)
    assert status.status == "sent"


@pytest.mark.asyncio
async def test_provider_registry_returns_none_when_mock_disabled(monkeypatch):
    monkeypatch.setenv("ENABLE_MOCK_RAILS", "false")

    reg = ProviderRegistry()
    req = QuoteRequest(
        sender_country="US",
        receiver_country="NG",
        amount=Decimal("250"),
        currency="USD",
        speed_preference="cheapest",
        payout_preference="bank",
        recipient_identifier=None,
    )
    corridor = CorridorCandidate(corridor_key="US->NG", available_rails=["ach"], confidence=1.0)

    quote = await reg.quote_route(request=req, corridor=corridor, rail_type="ach")
    assert quote is None

