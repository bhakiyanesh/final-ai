import time
from dataclasses import dataclass
from typing import Any

import httpx
from jose import jwt, jwk
from jose.exceptions import JWTError

from app.core.config import settings


@dataclass
class JwksCache:
    fetched_at: float = 0.0
    keys: list[dict[str, Any]] | None = None
    ttl_seconds: int = 300


_jwks_cache = JwksCache()


def _issuer() -> str:
    base = settings.supabase_url.rstrip("/")
    return settings.supabase_jwt_issuer or f"{base}/auth/v1"


async def _fetch_jwks() -> list[dict[str, Any]]:
    global _jwks_cache
    now = time.time()
    if _jwks_cache.keys is not None and now - _jwks_cache.fetched_at < _jwks_cache.ttl_seconds:
        return _jwks_cache.keys

    jwks_url = f"{settings.supabase_url.rstrip('/')}/auth/v1/keys"
    async with httpx.AsyncClient(timeout=10) as client:
        res = await client.get(jwks_url)
        res.raise_for_status()
        payload = res.json()

    keys = payload.get("keys", [])
    _jwks_cache = JwksCache(fetched_at=now, keys=keys, ttl_seconds=_jwks_cache.ttl_seconds)
    return keys


async def verify_supabase_access_token(token: str) -> dict[str, Any]:
    """
    Verifies a Supabase JWT using the project's JWKS.

    Returns decoded JWT claims; raises JWTError on invalid tokens.
    """
    unverified_header = jwt.get_unverified_header(token)
    kid = unverified_header.get("kid")
    alg = unverified_header.get("alg")
    if not kid or not alg:
        raise JWTError("Missing kid/alg in JWT header")

    keys = await _fetch_jwks()
    jwk_json = next((k for k in keys if k.get("kid") == kid), None)
    if jwk_json is None:
        raise JWTError("No matching JWKS key found for kid")

    key = jwk.construct(jwk_json)

    claims = jwt.decode(
        token,
        key,
        algorithms=[alg],
        audience=settings.supabase_jwt_audience,
        issuer=_issuer(),
    )
    return claims

