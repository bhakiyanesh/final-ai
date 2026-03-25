from __future__ import annotations

from typing import Any

import httpx

from app.core.config import settings


async def _chat_completion_openrouter(messages: list[dict[str, Any]], *, model: str) -> str:
    if not settings.llm_openrouter_api_key:
        raise RuntimeError("OPENROUTER_API_KEY not configured")
    if not model:
        raise RuntimeError("OPENROUTER model not configured")

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_openrouter_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(url, headers=headers, json=payload)
        res.raise_for_status()
        body = res.json()

    return body["choices"][0]["message"]["content"]


async def _chat_completion_ollama(messages: list[dict[str, Any]], *, model: str) -> str:
    base = settings.llm_ollama_base_url.rstrip("/")
    if not model:
        raise RuntimeError("OLLAMA model not configured")
    url = f"{base}/chat/completions"

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        # Ollama is often fast enough; keep tokens modest.
        "max_tokens": 512,
    }

    async with httpx.AsyncClient(timeout=30) as client:
        res = await client.post(url, json=payload)
        res.raise_for_status()
        body = res.json()

    return body["choices"][0]["message"]["content"]


async def chat_completion_with_fallback(messages: list[dict[str, Any]]) -> str:
    """
    Uses the configured primary LLM provider; falls back to the configured secondary.
    """
    primary = settings.llm_primary
    fallback = settings.llm_fallback

    primary_model = settings.llm_openrouter_model if primary == "openrouter" else settings.llm_ollama_model
    fallback_model = settings.llm_openrouter_model if fallback == "openrouter" else settings.llm_ollama_model

    # Try primary first
    try:
        if primary == "openrouter":
            return await _chat_completion_openrouter(messages, model=primary_model or "")
        if primary == "ollama":
            return await _chat_completion_ollama(messages, model=primary_model or "")
    except Exception:
        pass

    # Try fallback
    if fallback == "openrouter":
        return await _chat_completion_openrouter(messages, model=fallback_model or "")
    if fallback == "ollama":
        return await _chat_completion_ollama(messages, model=fallback_model or "")

    raise RuntimeError(f"Unsupported LLM providers: primary={primary}, fallback={fallback}")

