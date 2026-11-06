"""H3 Prompt Studio Security Middleware.

Enforces loopback-only binding, Host validation, and Origin validation
against DNS-rebinding and cross-site drive-by POST attacks.

Normative Reference: specification-0.3.md §5.7, Criterion A-35
"""

from __future__ import annotations

import re
from typing import Callable
from urllib.parse import urlparse

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

ALLOWED_HOSTNAMES = {"localhost", "127.0.0.1", "[::1]"}
MUTATING_METHODS = {"POST", "PUT", "DELETE", "PATCH"}


def extract_host(host_header: str) -> str:
    """Extract hostname without port from Host header (e.g. '127.0.0.1:9013' -> '127.0.0.1')."""
    if not host_header:
        return ""
    # IPv6 with port e.g. [::1]:9013
    if host_header.startswith("["):
        end_idx = host_header.find("]")
        if end_idx != -1:
            return host_header[: end_idx + 1]
    return host_header.split(":")[0].strip().lower()


def is_allowed_host(host_header: str) -> bool:
    """Return True if host is localhost, 127.0.0.1, or [::1]."""
    host = extract_host(host_header)
    return host in ALLOWED_HOSTNAMES


def is_allowed_origin(origin_header: str) -> bool:
    """Verify that Origin header host is loopback / localhost."""
    if not origin_header:
        return True
    try:
        parsed = urlparse(origin_header)
        hostname = (parsed.hostname or "").strip().lower()
        # Handle ipv6 brackets
        if hostname.startswith("[") and hostname.endswith("]"):
            return hostname in ALLOWED_HOSTNAMES
        return hostname in ALLOWED_HOSTNAMES
    except Exception:
        return False


class SecurityMiddleware(BaseHTTPMiddleware):
    """Middleware enforcing loopback Host and Origin validation."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # 1. Validate Host header
        host_header = request.headers.get("host", "").strip()
        if not is_allowed_host(host_header):
            return JSONResponse(
                status_code=403,
                content={
                    "error": {
                        "code": "forbidden",
                        "message": f"Forbidden: Host header '{host_header}' is not permitted.",
                    }
                },
            )

        # 2. Validate Origin header on mutating requests (CSRF / drive-by POST defence)
        if request.method in MUTATING_METHODS:
            origin_header = request.headers.get("origin", "").strip()
            if origin_header and not is_allowed_origin(origin_header):
                return JSONResponse(
                    status_code=403,
                    content={
                        "error": {
                            "code": "forbidden",
                            "message": f"Forbidden: Origin '{origin_header}' is not permitted.",
                        }
                    },
                )

        return await call_next(request)
