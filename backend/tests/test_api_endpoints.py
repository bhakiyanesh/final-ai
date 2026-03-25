import os
from decimal import Decimal
from typing import Any

import pytest
from fastapi.testclient import TestClient

# Enable auth bypass + deterministic provider quotes before importing app.
os.environ.setdefault("TEST_MODE", "true")
os.environ.setdefault("ENABLE_MOCK_RAILS", "true")

from app.main import app
from app.agents import fx_agent as fx_agent_module
from app.routers import transfers as transfers_module


@pytest.fixture()
def client():
    return TestClient(app)


def test_pricing_quote_endpoint_runs_graph_with_fx_fallback(monkeypatch, client: TestClient):
    async def _fail_best_fx_rate(*args, **kwargs):
        raise RuntimeError("FX sources unreachable")

    monkeypatch.setattr(fx_agent_module, "best_fx_rate", _fail_best_fx_rate)

    res = client.post(
        "/pricing/quote",
        json={
            "sender_country": "US",
            "receiver_country": "NG",
            "amount": 250,
            "currency": "USD",
            "speed_preference": "cheapest",
            "payout_preference": "bank",
            "recipient_identifier": None,
        },
    )

    assert res.status_code == 200
    body = res.json()
    assert body["delivery_method"] == "bank"
    assert body["fx_rate_snapshot"] == "1" or body["fx_rate_snapshot"] == 1


def test_transfers_create_is_idempotent(monkeypatch, client: TestClient):
    async def _fail_best_fx_rate(*args, **kwargs):
        raise RuntimeError("FX sources unreachable")

    monkeypatch.setattr(fx_agent_module, "best_fx_rate", _fail_best_fx_rate)

    existing_tx: dict[str, Any] | None = None
    route_id_counter = 0

    async def fake_select_one(*, table: str, access_token: str, params: dict[str, str]):
        nonlocal existing_tx
        if table == "transactions" and "idempotency_key" in params:
            return existing_tx
        return None

    async def fake_insert_one(*, table: str, access_token: str, row: dict[str, Any]):
        nonlocal existing_tx, route_id_counter
        if table == "transactions":
            tx_id = "00000000-0000-0000-0000-000000000123"
            existing_tx = {
                "id": tx_id,
                "status": row["status"],
                "quote_payload": row["quote_payload"],
            }
            return {"id": tx_id, "status": row["status"], "quote_payload": row["quote_payload"]}
        if table == "routes":
            route_id_counter += 1
            return {"id": f"00000000-0000-0000-0000-00000000{route_id_counter:04d}"}
        if table in {"fx_rates", "agents_logs"}:
            return {"id": f"00000000-0000-0000-0000-00000000{route_id_counter:04d}"}
        raise AssertionError(f"Unexpected insert table: {table}")

    async def fake_patch_many(*, table: str, access_token: str, filters: dict[str, str], patch: dict[str, Any]):
        return []

    monkeypatch.setattr(transfers_module, "select_one", fake_select_one)
    monkeypatch.setattr(transfers_module, "insert_one", fake_insert_one)
    monkeypatch.setattr(transfers_module, "patch_many", fake_patch_many)

    idem = "Idem12345"
    headers = {"Idempotency-Key": idem}

    payload = {
      "sender_country": "US",
      "receiver_country": "NG",
      "amount": 250,
      "currency": "USD",
      "speed_preference": "cheapest",
      "payout_preference": "bank",
      "recipient_identifier": None,
      "idempotency_key": idem,
    }

    res1 = client.post("/transfers", json=payload, headers=headers)
    assert res1.status_code == 200
    tx_id_1 = res1.json()["transaction_id"]

    res2 = client.post("/transfers", json=payload, headers=headers)
    assert res2.status_code == 200
    tx_id_2 = res2.json()["transaction_id"]

    assert tx_id_1 == tx_id_2
    assert res2.json()["status"] == "quoted"

