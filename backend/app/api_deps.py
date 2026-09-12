"""API dependencies: API-key auth, rate limiting (in-memory token bucket),
correlation IDs. Zero-trust: mutating endpoints always require admin auth;
reads optionally (spec §36/§37/§41)."""

from __future__ import annotations

import threading
import time
import uuid

from fastapi import Depends, Header, HTTPException, Request, status

from app.config import get_settings

_settings = get_settings()


class RateLimiter:
    """Simple per-client fixed-window limiter. Redis-backed in production."""

    MAX_TRACKED_CLIENTS = 10_000  # bound memory against unique-key floods

    def __init__(self, per_minute: int):
        self.per_minute = per_minute
        self._buckets: dict[str, tuple[int, float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            if len(self._buckets) > self.MAX_TRACKED_CLIENTS:
                # drop windows that expired — memory bound, not a rate decision
                self._buckets = {
                    k: v for k, v in self._buckets.items() if now - v[1] < 60.0
                }
                if len(self._buckets) > self.MAX_TRACKED_CLIENTS:
                    self._buckets.clear()
            count, window_start = self._buckets.get(key, (0, now))
            if now - window_start >= 60.0:
                count, window_start = 0, now
            if count >= self.per_minute:
                self._buckets[key] = (count, window_start)
                return False
            self._buckets[key] = (count + 1, window_start)
            return True


rate_limiter = RateLimiter(_settings.rate_limit_per_minute)


def client_key(request: Request) -> str:
    api_key = request.headers.get("X-API-Key", "")
    return api_key[:12] or (request.client.host if request.client else "anonymous")


def enforce_rate_limit(request: Request) -> None:
    if not rate_limiter.check(client_key(request)):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "rate_limit_exceeded", "message": "too many requests"},
        )


def require_admin_auth(x_api_key: str | None = Header(default=None)) -> str:
    """Auth for mutating endpoints. Constant-time-ish compare; key from env."""
    import hmac
    if not x_api_key or not hmac.compare_digest(x_api_key, _settings.admin_api_key):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "unauthorized", "message": "valid X-API-Key required"},
        )
    return "admin"


def require_read_auth(x_api_key: str | None = Header(default=None)) -> str:
    """Reads are open in development; can be locked with APP_READ_API_KEY."""
    if _settings.read_api_key:
        import hmac
        if not x_api_key or not hmac.compare_digest(x_api_key, _settings.read_api_key):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={"error": "unauthorized", "message": "valid X-API-Key required"},
            )
    return "reader"


def correlation_id(x_correlation_id: str | None = Header(default=None)) -> str:
    return x_correlation_id or uuid.uuid4().hex


class OptionalAuth:
    """Dependency bundle for read endpoints."""
    def __init__(self, request: Request, reader: str = Depends(require_read_auth)):
        enforce_rate_limit(request)
        self.reader = reader


class AdminAuth:
    """Dependency bundle for mutating endpoints (rate limit + admin key)."""
    def __init__(
        self,
        request: Request,
        admin: str = Depends(require_admin_auth),
    ):
        enforce_rate_limit(request)
        self.admin = admin
