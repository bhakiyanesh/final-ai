from __future__ import annotations

from decimal import Decimal

import httpx


class FxBestRateResult:
    def __init__(
        self,
        *,
        best_rate: Decimal,
        spread_fraction: Decimal,
        confidence: float,
        source_rates: dict[str, Decimal],
    ) -> None:
        self.best_rate = best_rate
        self.spread_fraction = spread_fraction
        self.confidence = confidence
        self.source_rates = source_rates


async def best_fx_rate(base_currency: str, quote_currency: str, *, timeout_s: int = 8) -> FxBestRateResult:
    """
    Best FX execution estimate by comparing multiple public sources.

    Returns:
      - best_rate: maximum of the fetched rates (maximizes payout for sender->recipient conversion)
      - spread_fraction: normalized disagreement between sources (proxy for FX spread)
      - confidence: 0..1 based on how many sources succeeded
    """
    base_currency = base_currency.strip().upper()
    quote_currency = quote_currency.strip().upper()

    async with httpx.AsyncClient(timeout=timeout_s) as client:
        rates: dict[str, Decimal] = {}

        # Source 1: open.er-api.com
        try:
            res = await client.get(f"https://open.er-api.com/v6/latest/{base_currency}")
            res.raise_for_status()
            payload = res.json()
            src_rate = payload.get("rates", {}).get(quote_currency)
            if src_rate is None:
                raise ValueError("Missing rate from open.er-api.com")
            rates["open_er_api"] = Decimal(str(src_rate))
        except Exception:
            pass

        # Source 2: frankfurter.app (from/to)
        try:
            res = await client.get(
                f"https://api.frankfurter.app/latest?from={base_currency}&to={quote_currency}"
            )
            res.raise_for_status()
            payload = res.json()
            src_rate = payload.get("rate")
            if src_rate is None:
                raise ValueError("Missing rate from frankfurter.app")
            rates["frankfurter"] = Decimal(str(src_rate))
        except Exception:
            pass

    if not rates:
        raise RuntimeError("No FX sources available")

    if len(rates) == 1:
        best_rate = next(iter(rates.values()))
        return FxBestRateResult(
            best_rate=best_rate,
            spread_fraction=Decimal("0"),
            confidence=0.5,
            source_rates=rates,
        )

    sorted_rates = sorted(rates.values())
    worst_rate, best_rate = sorted_rates[0], sorted_rates[-1]
    avg = (best_rate + worst_rate) / Decimal(2)
    spread_fraction = (best_rate - worst_rate) / avg if avg != 0 else Decimal("0")

    return FxBestRateResult(
        best_rate=best_rate,
        spread_fraction=spread_fraction,
        confidence=0.85,
        source_rates=rates,
    )

