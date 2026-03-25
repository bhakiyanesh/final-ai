from __future__ import annotations

from decimal import Decimal
from typing import Any, Literal

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from app.agents.quote_graph import run_pricing_quote
from app.agents.types import PricingQuoteResponse, RouteCandidate
from app.models.transfer import CreateTransferRequest, QuoteRequest
from app.providers.registry import ProviderRegistry
from app.supabase.rest_client import insert_one, patch_many, select_many, select_one

router = APIRouter()


class TransferCreateResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    status: str
    quote: PricingQuoteResponse


class TransferExecuteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    status: str
    provider_reference: str


class TransferStatusResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_id: str
    status: str
    quote: PricingQuoteResponse


def _parse_quote_for_model(quote_payload: dict[str, Any]) -> dict[str, Any]:
    # PricingQuoteResponse has `extra="forbid"`, so we strip execution-only metadata.
    cleaned = dict(quote_payload)
    cleaned.pop("_execution", None)
    return cleaned


def _map_provider_status(provider_status: str) -> str:
    if provider_status in {"failed", "cancelled"}:
        return provider_status
    if provider_status in {"created", "executing"}:
        return "executing"
    if provider_status in {"sent"}:
        return "sent"
    # Default safe mapping
    return "executing"


@router.post("/transfers", response_model=TransferCreateResponse)
async def create_transfer(request: Request, body: CreateTransferRequest) -> TransferCreateResponse:
    access_token = request.state.access_token
    user_id = request.state.user_id

    # Ensure the idempotency key header matches the body (prevents bypassing replay protections).
    idem_key_header = request.headers.get("Idempotency-Key")
    if idem_key_header and idem_key_header != body.idempotency_key:
        raise HTTPException(status_code=400, detail="Idempotency key mismatch")

    # Idempotency: return existing transaction if the same key already created one.
    existing = await select_one(
        table="transactions",
        access_token=access_token,
        params={
            "user_id": f"eq.{user_id}",
            "idempotency_key": f"eq.{body.idempotency_key}",
            "select": "id,status,quote_payload",
        },
    )
    if existing:
        quote = PricingQuoteResponse.model_validate(existing["quote_payload"])
        return TransferCreateResponse(
            transaction_id=str(existing["id"]),
            status=str(existing["status"]),
            quote=quote,
        )

    quote_request = QuoteRequest.model_validate(body.model_dump(exclude={"idempotency_key"}))
    quote = await run_pricing_quote(quote_request)

    quote_json = quote.model_dump(mode="json")

    tx_row = {
        "user_id": user_id,
        "idempotency_key": body.idempotency_key,
        "sender_country": body.sender_country,
        "receiver_country": body.receiver_country,
        "amount": str(body.amount),
        "currency": body.currency,
        "speed_preference": body.speed_preference,
        "payout_preference": body.payout_preference,
        "recipient_identifier": body.recipient_identifier,
        "status": "quoted",
        "quote_payload": quote_json,
        "selected_route_id": None,
        "total_fee": quote_json["total_fee"],
        "fx_rate": quote_json["fx_rate_snapshot"],
        "fx_spread": quote_json["fx_spread"],
        "all_in_total": quote_json["all_in_total"],
        "delivery_eta_seconds": quote_json["delivery_eta_seconds"],
    }

    tx = await insert_one(table="transactions", access_token=access_token, row=tx_row)
    tx_id = str(tx["id"])

    # Insert route alternatives for transparency.
    recommended = quote.recommended_route
    recommended_match = lambda rc: (
        rc.rail_type == recommended.rail_type
        and rc.corridor_key == recommended.corridor_key
        and rc.fee_total == recommended.fee_total
        and rc.eta_seconds == recommended.eta_seconds
    )

    recommended_route_id: str | None = None
    for rc in quote.route_alternatives:
        rc_json = rc.model_dump(mode="json")
        is_recommended = recommended_match(rc)
        if is_recommended:
            recommended_route_id = None  # set once inserted
        route_row = {
            "transaction_id": tx_id,
            "corridor_key": rc_json["corridor_key"],
            "rail_type": rc_json["rail_type"],
            "provider_path": rc_json["provider_path"],
            "fee_total": rc_json["fee_total"],
            "fx_rate": rc_json["fx_rate"],
            "fx_spread": rc_json["fx_spread"] if rc_json["fx_spread"] is not None else "0",
            "eta_seconds": rc_json["eta_seconds"],
            "cost_vs_speed_score": rc_json["cost_score"],
            "confidence": rc_json["confidence"],
            "is_recommended": is_recommended,
        }
        inserted = await insert_one(table="routes", access_token=access_token, row=route_row)
        if is_recommended:
            recommended_route_id = str(inserted["id"])

    # Backfill the selected route id on the transaction row.
    if recommended_route_id:
        await patch_many(
            table="transactions",
            access_token=access_token,
            filters={"id": f"eq.{tx_id}"},
            patch={"selected_route_id": recommended_route_id},
        )

    # Insert an FX-rate snapshot for audit.
    fx_quote = quote.fx_rate_snapshot
    if fx_quote is not None:
        await insert_one(
            table="fx_rates",
            access_token=access_token,
            row={
                "transaction_id": tx_id,
                "base_currency": body.currency,
                "quote_currency": quote.recommended_route.payout_currency,
                "source": "fx_proxy_open_er_api_and_frankfurter",
                "rate": quote.fx_rate_snapshot,
                "spread": quote.fx_spread if quote.fx_spread is not None else Decimal("0"),
                "valid_until": None,
                "metadata": {"generated_by": "FXAgent"},
            },
        )

    # Store the AI explanation in agents_logs for auditability.
    if quote.ai_explanation:
        await insert_one(
            table="agents_logs",
            access_token=access_token,
            row={
                "transaction_id": tx_id,
                "user_id": user_id,
                "agent_name": "LastMileAgent",
                "step_name": "ai_explanation",
                "trace_id": None,
                "input_json": {
                    "speed_preference": body.speed_preference,
                    "payout_preference": body.payout_preference,
                },
                "output_json": {"ai_explanation": quote.ai_explanation},
                "confidence": quote.confidence,
                "error_json": None,
            },
        )

    return TransferCreateResponse(
        transaction_id=tx_id,
        status="quoted",
        quote=quote,
    )


@router.post("/transfers/{transaction_id}/execute", response_model=TransferExecuteResponse)
async def execute_transfer(
    request: Request,
    transaction_id: str,
) -> TransferExecuteResponse:
    access_token = request.state.access_token
    user_id = request.state.user_id
    idem_key_header = request.headers.get("Idempotency-Key")  # validated by middleware

    tx = await select_one(
        table="transactions",
        access_token=access_token,
        params={
            "id": f"eq.{transaction_id}",
            "user_id": f"eq.{user_id}",
            "select": "id,status,selected_route_id,quote_payload,payout_preference,recipient_identifier,sender_country,receiver_country,amount,currency,speed_preference",
        },
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    if tx["status"] not in {"quoted", "executing"}:
        raise HTTPException(status_code=400, detail=f"Cannot execute transaction in status {tx['status']}")

    # Replay defense: if we already executed with the same idempotency key, return.
    quote_payload = tx.get("quote_payload") or {}
    exec_meta = quote_payload.get("_execution") or {}
    if exec_meta and idem_key_header and exec_meta.get("idempotency_key") == idem_key_header:
        return TransferExecuteResponse(
            transaction_id=str(tx["id"]),
            status=str(tx["status"]),
            provider_reference=str(exec_meta.get("provider_reference", "")),
        )

    # Determine selected route (rail type) to execute.
    rail_type = None
    if tx.get("selected_route_id"):
        route = await select_one(
            table="routes",
            access_token=access_token,
            params={
                "id": f"eq.{tx['selected_route_id']}",
                "transaction_id": f"eq.{transaction_id}",
                "select": "id,rail_type,provider_path",
            },
        )
        if route:
            rail_type = route.get("rail_type")

    if not rail_type:
        route = await select_one(
            table="routes",
            access_token=access_token,
            params={
                "transaction_id": f"eq.{transaction_id}",
                "is_recommended": "eq.true",
                "select": "id,rail_type,provider_path",
            },
        )
        if route:
            rail_type = route.get("rail_type")

    if not rail_type:
        raise HTTPException(status_code=500, detail="No recommended route found for transaction")

    provider_registry = ProviderRegistry()
    execute_payload = {
        "transaction_id": transaction_id,
        "sender_country": tx["sender_country"],
        "receiver_country": tx["receiver_country"],
        "amount": str(tx["amount"]),
        "currency": tx["currency"],
        "speed_preference": tx["speed_preference"],
        "payout_preference": tx["payout_preference"],
        "recipient_identifier": tx["recipient_identifier"],
        "quote_payload": tx.get("quote_payload"),
    }

    exec_result = await provider_registry.execute_transfer(
        rail_type=rail_type,
        execute_payload=execute_payload,
    )

    new_status = _map_provider_status(exec_result.status)
    quote_payload = tx.get("quote_payload") or {}
    quote_payload["_execution"] = {
        "provider_reference": exec_result.provider_reference,
        "provider_status": exec_result.status,
        "idempotency_key": idem_key_header,
        "provider_metadata": exec_result.provider_metadata,
    }

    await patch_many(
        table="transactions",
        access_token=access_token,
        filters={"id": f"eq.{transaction_id}"},
        patch={
            "status": new_status,
            "quote_payload": quote_payload,
        },
    )

    return TransferExecuteResponse(
        transaction_id=str(tx["id"]),
        status=new_status,
        provider_reference=exec_result.provider_reference,
    )


@router.get("/transfers/{transaction_id}", response_model=TransferStatusResponse)
async def get_transfer(
    request: Request,
    transaction_id: str,
) -> TransferStatusResponse:
    access_token = request.state.access_token
    user_id = request.state.user_id

    tx = await select_one(
        table="transactions",
        access_token=access_token,
        params={
            "id": f"eq.{transaction_id}",
            "user_id": f"eq.{user_id}",
            "select": "id,status,quote_payload",
        },
    )
    if not tx:
        raise HTTPException(status_code=404, detail="Transaction not found")

    quote_payload = tx.get("quote_payload") or {}
    quote = PricingQuoteResponse.model_validate(_parse_quote_for_model(quote_payload))

    # Optional live status refresh (if provider_reference is present).
    exec_meta = quote_payload.get("_execution") or {}
    provider_reference = exec_meta.get("provider_reference")
    rail_type = None

    if provider_reference:
        selected_route_id = None
        # Lightweight lookup for rail_type.
        selected_route = await select_one(
            table="routes",
            access_token=access_token,
            params={
                "transaction_id": f"eq.{transaction_id}",
                "is_recommended": "eq.true",
                "select": "rail_type",
            },
        )
        if selected_route:
            rail_type = selected_route.get("rail_type")

    if provider_reference and rail_type:
        provider_registry = ProviderRegistry()
        try:
            st = await provider_registry.get_provider_status(
                rail_type=rail_type,
                provider_reference=provider_reference,
            )
            # Update stored status if it differs.
            provider_mapped = _map_provider_status(st.status)
            if provider_mapped != tx["status"] or st.eta_seconds is not None:
                patch = {"status": provider_mapped}
                if st.eta_seconds is not None:
                    patch["delivery_eta_seconds"] = st.eta_seconds
                await patch_many(
                    table="transactions",
                    access_token=access_token,
                    filters={"id": f"eq.{transaction_id}"},
                    patch=patch,
                )
                tx["status"] = provider_mapped
        except Exception:
            # If provider status refresh fails, return stored status.
            pass

    return TransferStatusResponse(
        transaction_id=str(tx["id"]),
        status=str(tx["status"]),
        quote=quote,
    )

