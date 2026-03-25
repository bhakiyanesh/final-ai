from fastapi import APIRouter

from app.agents.quote_graph import run_pricing_quote
from app.agents.types import PricingQuoteResponse
from app.models.transfer import QuoteRequest

router = APIRouter()


@router.post("/pricing/quote", response_model=PricingQuoteResponse)
async def quote(body: QuoteRequest) -> PricingQuoteResponse:
    return await run_pricing_quote(body)

