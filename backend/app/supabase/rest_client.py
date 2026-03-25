from __future__ import annotations

import json
from typing import Any, Iterable

import httpx

from app.core.config import settings


SUPPORTED_TABLES = {"users", "transactions", "routes", "fx_rates", "agents_logs"}


def _rest_url(path: str) -> str:
    return f"{settings.supabase_url.rstrip('/')}/rest/v1/{path.lstrip('/')}"


def _headers(access_token: str) -> dict[str, str]:
    if not settings.supabase_anon_key:
        raise RuntimeError("SUPABASE_ANON_KEY not configured")
    return {
        "apikey": settings.supabase_anon_key,
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }


async def select_one(*, table: str, access_token: str, params: dict[str, str]) -> dict[str, Any] | None:
    if table not in SUPPORTED_TABLES:
        raise ValueError("Unsupported table")

    url = _rest_url(table)
    query = dict(params)
    query.setdefault("select", "*")

    async with httpx.AsyncClient(timeout=settings.supabase_rest_timeout_s) as client:
        res = await client.get(url, params=query, headers=_headers(access_token))
        res.raise_for_status()
        body = res.json()
        if not body:
            return None
        return body[0]


async def select_many(*, table: str, access_token: str, params: dict[str, str]) -> list[dict[str, Any]]:
    if table not in SUPPORTED_TABLES:
        raise ValueError("Unsupported table")

    url = _rest_url(table)
    query = dict(params)
    query.setdefault("select", "*")

    async with httpx.AsyncClient(timeout=settings.supabase_rest_timeout_s) as client:
        res = await client.get(url, params=query, headers=_headers(access_token))
        res.raise_for_status()
        body = res.json()
        if body is None:
            return []
        return list(body)


async def insert_one(
    *,
    table: str,
    access_token: str,
    row: dict[str, Any],
) -> dict[str, Any]:
    if table not in SUPPORTED_TABLES:
        raise ValueError("Unsupported table")

    url = _rest_url(table)
    headers = _headers(access_token)
    headers["Prefer"] = "return=representation"

    async with httpx.AsyncClient(timeout=settings.supabase_rest_timeout_s) as client:
        res = await client.post(url, headers=headers, json=row)
        res.raise_for_status()
        body = res.json()
        if not body:
            raise RuntimeError("Insert returned no rows")
        # PostgREST typically returns an array for inserts.
        if isinstance(body, list):
            return body[0]
        return body


async def patch_many(
    *,
    table: str,
    access_token: str,
    filters: dict[str, str],
    patch: dict[str, Any],
) -> list[dict[str, Any]]:
    if table not in SUPPORTED_TABLES:
        raise ValueError("Unsupported table")

    url = _rest_url(table)
    headers = _headers(access_token)
    headers["Prefer"] = "return=representation"

    async with httpx.AsyncClient(timeout=settings.supabase_rest_timeout_s) as client:
        res = await client.patch(url, headers=headers, params=filters, json=patch)
        res.raise_for_status()
        body = res.json()
        if body is None:
            return []
        if isinstance(body, list):
            return body
        return [body]

