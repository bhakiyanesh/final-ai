from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.core.config import settings
from app.middleware.supabase_auth import SupabaseAuthMiddleware

from app.routers.health import router as health_router
from app.routers.pricing import router as pricing_router
from app.routers.transfers import router as transfers_router


def create_app() -> FastAPI:
    app = FastAPI(title="Agent API", version="0.1.0")

    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    if not origins:
        origins = ["http://localhost:3000"]

    limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[settings.rate_limit_default],
    )
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # Rate limiting runs at the ASGI middleware layer.
    app.add_middleware(SlowAPIMiddleware)

    # JWT validation + replay defense.
    app.add_middleware(SupabaseAuthMiddleware)

    # Allow browser -> backend requests (Authorization header is required).
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health_router)
    app.include_router(pricing_router)
    app.include_router(transfers_router)
    return app


app = create_app()

