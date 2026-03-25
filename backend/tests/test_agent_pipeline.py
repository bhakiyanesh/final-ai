import os
from decimal import Decimal

import pytest

# Ensure test mode + deterministic provider quotes before importing app settings.
os.environ.setdefault("TEST_MODE", "true")
os.environ.setdefault("ENABLE_MOCK_RAILS", "true")

from app.agents.quote_graph import run_pricing_quote
from app.agents import fx_agent as fx_agent_module
from app.models.transfer import QuoteRequest


@pytest.mark.asyncio
async def test_graph_fx_fallback(monkeypatch):
    async def _fail_best_fx_rate(*args, **kwargs):
        raise RuntimeError("FX sources unreachable")

    monkeypatch.setattr(fx_agent_module, "best_fx_rate", _fail_best_fx_rate)

    req = QuoteRequest(
        sender_country="US",
        receiver_country="NG",
        amount=Decimal("250"),
        currency="USD",
        speed_preference="cheapest",
        payout_preference="bank",
        recipient_identifier=None,
    )

    resp = await run_pricing_quote(req)

    assert resp.fx_rate_snapshot == Decimal("1")
    assert resp.fx_spread == Decimal("0")
    assert resp.all_in_total == resp.request.amount + resp.total_fee
    assert resp.delivery_method == "bank"

