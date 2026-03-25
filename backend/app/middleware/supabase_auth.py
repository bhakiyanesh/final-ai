from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.status import HTTP_400_BAD_REQUEST, HTTP_401_UNAUTHORIZED

from app.core.config import settings
from app.core.security.idempotency import validate_idempotency_key
from app.core.security.supabase_jwt import verify_supabase_access_token


class SupabaseAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path or ""
        if path.startswith("/health"):
            return await call_next(request)

        if settings.test_mode:
            # Test-only bypass for JWT verification.
            request.state.user_id = settings.test_user_id
            request.state.access_token = "test-token"

            if request.method in {"POST", "PUT", "PATCH", "DELETE"} and path.startswith(
                "/transfers"
            ):
                idem = request.headers.get(settings.idempotency_key_header)
                if not idem:
                    return JSONResponse(
                        {"error": f"Missing {settings.idempotency_key_header} header"},
                        status_code=HTTP_400_BAD_REQUEST,
                    )
                try:
                    request.state.idempotency_key = validate_idempotency_key(idem)
                except ValueError as e:
                    return JSONResponse(
                        {"error": f"Invalid {settings.idempotency_key_header}: {str(e)}"},
                        status_code=HTTP_400_BAD_REQUEST,
                    )
            return await call_next(request)

        auth_header = request.headers.get("authorization")
        if not auth_header or not auth_header.lower().startswith("bearer "):
            return JSONResponse(
                {"error": "Unauthorized: missing Bearer token"},
                status_code=HTTP_401_UNAUTHORIZED,
            )

        token = auth_header.split(" ", 1)[1].strip()
        if not token:
            return JSONResponse(
                {"error": "Unauthorized: empty token"},
                status_code=HTTP_401_UNAUTHORIZED,
            )

        try:
            claims = await verify_supabase_access_token(token)
        except Exception:
            return JSONResponse(
                {"error": "Unauthorized: invalid token"},
                status_code=HTTP_401_UNAUTHORIZED,
            )

        # Supabase access tokens use `sub` as the user UUID.
        user_id = claims.get("sub") or claims.get("user_id")
        if not user_id:
            return JSONResponse(
                {"error": "Unauthorized: token missing subject"},
                status_code=HTTP_401_UNAUTHORIZED,
            )

        request.state.user_id = user_id
        request.state.access_token = token

        # Replay protection: require idempotency key for transfer state changes only.
        if request.method in {"POST", "PUT", "PATCH", "DELETE"} and path.startswith("/transfers"):
            idem = request.headers.get(settings.idempotency_key_header)
            if not idem:
                return JSONResponse(
                    {"error": f"Missing {settings.idempotency_key_header} header"},
                    status_code=HTTP_400_BAD_REQUEST,
                )
            try:
                request.state.idempotency_key = validate_idempotency_key(idem)
            except ValueError as e:
                return JSONResponse(
                    {"error": f"Invalid {settings.idempotency_key_header}: {str(e)}"},
                    status_code=HTTP_400_BAD_REQUEST,
                )

        return await call_next(request)

