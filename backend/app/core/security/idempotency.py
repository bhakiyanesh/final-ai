import re

from app.core.config import settings

IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9:_-]+$")


def validate_idempotency_key(value: str) -> str:
    value = value.strip()
    if not (settings.idempotency_key_min_len <= len(value) <= settings.idempotency_key_max_len):
        raise ValueError("Invalid idempotency key length")
    if not IDEMPOTENCY_KEY_RE.fullmatch(value):
        raise ValueError("Invalid idempotency key format")
    return value

