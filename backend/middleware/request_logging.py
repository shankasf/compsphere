"""
Request logging middleware for FastAPI.

Provides:
- Unique request ID generation (X-Request-ID header)
- Request/response timing
- Structured logging of every HTTP request
- Unhandled exception capture with full traceback
- User ID extraction from JWT (when available)
"""

import time
import uuid
import traceback

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from core.logging_config import get_logger, request_id_var, user_id_var

logger = get_logger("compsphere.middleware")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Logs every HTTP request with timing, status, and correlation ID."""

    # Paths that generate too much noise at INFO level
    QUIET_PATHS = {"/api/health"}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Generate or accept a request ID
        rid = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        request_id_var.set(rid)

        # Try to extract user_id from auth header (best effort, no DB call)
        self._extract_user_id(request)

        method = request.method
        path = request.url.path
        client_ip = request.client.host if request.client else "-"
        query = str(request.url.query) if request.url.query else ""

        start = time.perf_counter()

        try:
            response = await call_next(request)
            duration_ms = round((time.perf_counter() - start) * 1000, 2)

            # Add request ID to response headers for client-side correlation
            response.headers["X-Request-ID"] = rid

            log_extra = {
                "method": method,
                "endpoint": path,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
                "client_ip": client_ip,
            }

            if path in self.QUIET_PATHS:
                logger.debug(
                    f"{method} {path} -> {response.status_code} ({duration_ms}ms)",
                    extra=log_extra,
                )
            elif response.status_code >= 500:
                logger.error(
                    f"{method} {path} -> {response.status_code} ({duration_ms}ms)",
                    extra=log_extra,
                )
            elif response.status_code >= 400:
                logger.warning(
                    f"{method} {path} -> {response.status_code} ({duration_ms}ms)",
                    extra=log_extra,
                )
            else:
                logger.info(
                    f"{method} {path} -> {response.status_code} ({duration_ms}ms)",
                    extra=log_extra,
                )

            return response

        except Exception as exc:
            duration_ms = round((time.perf_counter() - start) * 1000, 2)
            logger.error(
                f"Unhandled exception: {method} {path} ({duration_ms}ms) - {type(exc).__name__}: {exc}",
                exc_info=True,
                extra={
                    "method": method,
                    "endpoint": path,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                    "error_context": traceback.format_exc(),
                },
            )
            return JSONResponse(
                status_code=500,
                content={"detail": "Internal server error"},
                headers={"X-Request-ID": rid},
            )

    def _extract_user_id(self, request: Request) -> None:
        """Best-effort extraction of user_id from the JWT token."""
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return
        token = auth_header[7:]
        try:
            # Decode without verification just to extract sub claim for logging
            import base64
            import json as json_mod
            payload_part = token.split(".")[1]
            # Add padding
            payload_part += "=" * (4 - len(payload_part) % 4)
            payload = json_mod.loads(base64.urlsafe_b64decode(payload_part))
            uid = payload.get("sub", "-")
            user_id_var.set(uid)
        except Exception:
            pass
