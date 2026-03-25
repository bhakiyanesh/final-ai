import hashlib
import json
import os
from dataclasses import dataclass
from decimal import Decimal

from app.agents.types import CorridorCandidate, RailType, RouteQuote
from app.models.transfer import QuoteRequest
from app.providers.http_adapter import HttpProviderAdapter
from app.providers.types import ProviderExecutionResult, ProviderStatusResult


@dataclass(frozen=True)
class MockRailConfig:
    enabled: bool
    stablecoin_fee_bps: Decimal
    stablecoin_fixed_fee: Decimal
    stablecoin_eta_seconds: int

    ach_fee_bps: Decimal
    ach_fixed_fee: Decimal
    ach_eta_seconds: int

    mobile_fee_bps: Decimal
    mobile_fixed_fee: Decimal
    mobile_eta_seconds: int


def _env_bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "y", "on"}


def _env_decimal(name: str, default: str) -> Decimal:
    return Decimal(str(os.getenv(name, default)))


def _env_json_map(name: str) -> dict[str, str]:
    raw = os.getenv(name)
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {}
        # Ensure values are strings.
        return {str(k): str(v) for k, v in parsed.items()}
    except Exception:
        return {}


class ProviderRegistry:
    """
    Provider registry abstraction for rail quote + execution.

    For local dev, this implementation supports optional mock quotes via env.
    Real provider adapters will be added in the next task.
    """

    def __init__(self) -> None:
        self._cfg = MockRailConfig(
            enabled=_env_bool("ENABLE_MOCK_RAILS", default=False),
            stablecoin_fee_bps=_env_decimal("MOCK_STABLECOIN_FEE_BPS", "50"),  # 0.50%
            stablecoin_fixed_fee=_env_decimal("MOCK_STABLECOIN_FIXED_FEE", "1.0"),
            stablecoin_eta_seconds=int(os.getenv("MOCK_STABLECOIN_ETA_SECONDS", "300")),
            ach_fee_bps=_env_decimal("MOCK_ACH_FEE_BPS", "100"),  # 1.00%
            ach_fixed_fee=_env_decimal("MOCK_ACH_FIXED_FEE", "2.0"),
            ach_eta_seconds=int(os.getenv("MOCK_ACH_ETA_SECONDS", "86400")),
            mobile_fee_bps=_env_decimal("MOCK_MOBILE_FEE_BPS", "150"),  # 1.50%
            mobile_fixed_fee=_env_decimal("MOCK_MOBILE_FIXED_FEE", "1.5"),
            mobile_eta_seconds=int(os.getenv("MOCK_MOBILE_ETA_SECONDS", "172800")),
        )

        quote_urls = _env_json_map("RAIL_HTTP_QUOTE_URLS")
        execute_urls = _env_json_map("RAIL_HTTP_EXECUTE_URLS")
        status_urls = _env_json_map("RAIL_HTTP_STATUS_URLS")

        adapters: dict[RailType, HttpProviderAdapter] = {}
        for rail_key, quote_url in quote_urls.items():
            # Only accept known rail keys.
            if rail_key not in {"stablecoin", "ach", "mobile_money"}:
                continue
            rail_type = rail_key  # type: ignore[assignment]
            adapters[rail_type] = HttpProviderAdapter(
                rail_type=rail_type,
                quote_url=quote_url,
                execute_url=execute_urls.get(rail_key),
                status_url=status_urls.get(rail_key),
            )

        self._adapters_by_rail = adapters

    def get_viable_rails(self, request: QuoteRequest) -> list[RailType]:
        """
        Simple mapping from payout preference to likely rails.
        (Country-specific routing will be connected to real providers later.)
        """
        if request.payout_preference == "stablecoin":
            rails: list[RailType] = ["stablecoin"]
        elif request.payout_preference == "bank":
            rails = ["ach"]
        elif request.payout_preference == "mobile":
            rails = ["mobile_money"]
        elif request.payout_preference == "cash":
            rails = ["mobile_money"]  # common cashout proxy in low-infrastructure settings
        else:
            rails = []

        def rail_available(r: RailType) -> bool:
            return r in self._adapters_by_rail or self._cfg.enabled

        return [r for r in rails if rail_available(r)]

    async def quote_route(
        self,
        *,
        request: QuoteRequest,
        corridor: CorridorCandidate,
        rail_type: RailType,
    ) -> RouteQuote | None:
        adapter = self._adapters_by_rail.get(rail_type)
        if adapter is not None:
            q = await adapter.quote_route(request=request, corridor_key=corridor.corridor_key)
            return RouteQuote(
                corridor_key=corridor.corridor_key,
                rail_type=rail_type,
                fee_total=q.fee_total,
                eta_seconds=q.eta_seconds,
                liquidity_confidence=q.liquidity_confidence,
                payout_currency=q.payout_currency,
                provider_path=q.provider_path,
                provider_metadata=q.provider_metadata,
            )

        if not self._cfg.enabled:
            return None

        amount = request.amount
        if rail_type == "stablecoin":
            fee_total = (amount * self._cfg.stablecoin_fee_bps) / Decimal(10_000) + self._cfg.stablecoin_fixed_fee
            liquidity_conf = self._liquidity_confidence(amount)
            return RouteQuote(
                corridor_key=corridor.corridor_key,
                rail_type=rail_type,
                fee_total=fee_total,
                eta_seconds=max(60, int(self._cfg.stablecoin_eta_seconds * (1 + (1 - liquidity_conf)))),
                liquidity_confidence=liquidity_conf,
                payout_currency=request.currency,  # for mock we keep 1:1
                provider_path=["mock-stablecoin-rail"],
                provider_metadata={"mock": True},
            )

        if rail_type == "ach":
            fee_total = (amount * self._cfg.ach_fee_bps) / Decimal(10_000) + self._cfg.ach_fixed_fee
            liquidity_conf = self._liquidity_confidence(amount)
            return RouteQuote(
                corridor_key=corridor.corridor_key,
                rail_type=rail_type,
                fee_total=fee_total,
                eta_seconds=max(3600, int(self._cfg.ach_eta_seconds * (1 + (1 - liquidity_conf)))),
                liquidity_confidence=liquidity_conf,
                payout_currency=request.currency,
                provider_path=["mock-ach-rail"],
                provider_metadata={"mock": True},
            )

        if rail_type == "mobile_money":
            fee_total = (amount * self._cfg.mobile_fee_bps) / Decimal(10_000) + self._cfg.mobile_fixed_fee
            liquidity_conf = self._liquidity_confidence(amount)
            return RouteQuote(
                corridor_key=corridor.corridor_key,
                rail_type=rail_type,
                fee_total=fee_total,
                eta_seconds=max(7200, int(self._cfg.mobile_eta_seconds * (1 + (1 - liquidity_conf)))),
                liquidity_confidence=liquidity_conf,
                payout_currency=request.currency,
                provider_path=["mock-mobile-money-rail"],
                provider_metadata={"mock": True},
            )

        return None

    async def execute_transfer(
        self,
        *,
        rail_type: RailType,
        execute_payload: dict,
    ) -> ProviderExecutionResult:
        adapter = self._adapters_by_rail.get(rail_type)
        if adapter is None:
            if self._cfg.enabled:
                raw = json.dumps(execute_payload, sort_keys=True, default=str)
                ref = f"mock-{rail_type}-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
                return ProviderExecutionResult(
                    provider_reference=ref,
                    status="sent",
                    provider_metadata={"mock": True, "execute_payload": execute_payload},
                )
            raise RuntimeError(f"No adapter configured for rail: {rail_type}")
        return await adapter.execute(execute_payload=execute_payload)

    async def get_provider_status(
        self,
        *,
        rail_type: RailType,
        provider_reference: str,
    ) -> ProviderStatusResult:
        adapter = self._adapters_by_rail.get(rail_type)
        if adapter is None:
            if self._cfg.enabled:
                return ProviderStatusResult(
                    provider_reference=provider_reference,
                    status="sent",
                    eta_seconds=None,
                    provider_metadata={"mock": True},
                )
            raise RuntimeError(f"No adapter configured for rail: {rail_type}")
        return await adapter.status(provider_reference=provider_reference)

    @staticmethod
    def _liquidity_confidence(amount: Decimal) -> float:
        # Mock liquidity confidence: smaller transfers have fewer liquidity constraints.
        # This will later be replaced by provider liquidity signals.
        if amount <= 100:
            return 0.92
        if amount <= 1000:
            return 0.82
        if amount <= 10_000:
            return 0.7
        return 0.55

