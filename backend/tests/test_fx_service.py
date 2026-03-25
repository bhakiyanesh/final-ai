from decimal import Decimal

import httpx
import pytest

from app.agents.fx_service import best_fx_rate


class DummyResponse:
    def __init__(self, payload, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError("HTTP error")

    def json(self):
        return self._payload


class DummyClient:
    def __init__(self, timeout: int) -> None:
        self.timeout = timeout

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url: str):
        if "open.er-api.com" in url:
            return DummyResponse({"rates": {"EUR": "0.90"}})
        if "api.frankfurter.app" in url:
            return DummyResponse({"rate": "0.95"})
        return DummyResponse({}, status_code=404)


@pytest.mark.asyncio
async def test_best_fx_rate_uses_max_and_spread(monkeypatch):
    monkeypatch.setattr(httpx, "AsyncClient", DummyClient)

    res = await best_fx_rate("USD", "EUR")

    assert res.best_rate == Decimal("0.95")
    # Spread proxy should be > 0 because sources disagree.
    assert res.spread_fraction > 0
    assert res.confidence == 0.85
    assert set(res.source_rates.keys()) == {"open_er_api", "frankfurter"}

