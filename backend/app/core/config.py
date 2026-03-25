from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Supabase
    # Default allows local health checks without env vars.
    supabase_url: str = "http://localhost:54321"
    supabase_anon_key: str | None = None
    supabase_rest_timeout_s: int = 15
    supabase_jwt_audience: str = "authenticated"
    supabase_jwt_issuer: str | None = None  # if not set, derived from supabase_url

    # Rate limiting
    rate_limit_default: str = "60/minute"

    # Idempotency / replay protection
    idempotency_key_header: str = "Idempotency-Key"
    idempotency_key_min_len: int = 8
    idempotency_key_max_len: int = 128

    # LLM providers (optional; if not configured, ai_explanation will be omitted)
    llm_primary: str = "openrouter"  # openrouter | ollama
    llm_openrouter_api_key: str | None = None
    llm_openrouter_model: str | None = None

    llm_fallback: str = "ollama"
    llm_ollama_base_url: str = "http://localhost:11434/v1"
    llm_ollama_model: str | None = None

    # LangSmith (optional)
    langsmith_project: str = "remittance-mvp"

    # Test-only controls (do not enable in production).
    test_mode: bool = False
    test_user_id: str = "00000000-0000-0000-0000-000000000000"

    # CORS (browser -> FastAPI). Comma-separated list, e.g. "http://localhost:3000,https://yourdomain.com".
    cors_origins: str = "http://localhost:3000"



settings = Settings()

