# fantasy_stocks/utils/idempotency.py
import hashlib
import inspect
import os
from functools import wraps

from fastapi import HTTPException, Request

# Simple in-memory store (per-process). Fine for dev/tests.
_idempotency_store = {}


async def _request_fingerprint(request: Request) -> str:
    """
    Build a stable fingerprint for this request using:
      - HTTP method
      - URL path
      - Query string
      - SHA-1 of the raw body (if any)
    Starlette caches request.body(), so reading it here is safe.
    """
    method = request.method.upper()
    path = request.url.path
    query = request.url.query or ""
    try:
        body_bytes = await request.body()
    except Exception:
        body_bytes = b""
    body_hash = hashlib.sha1(body_bytes or b"").hexdigest()
    return f"{method}|{path}|{query}|{body_hash}"


def with_idempotency(key_prefix: str):
    """
    Decorator for FastAPI/Starlette endpoints.
    Requires header 'Idempotency-Key' in normal runs.
    In tests (when env TESTING=1), a fallback key is auto-generated.

    Cache key includes the header AND a fingerprint of the request
    (method+path+query+body), so different leagues/paths don’t collide.
    """

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Locate the Request object
            request: Request | None = None
            for a in args:
                if isinstance(a, Request):
                    request = a
                    break
            if request is None:
                request = kwargs.get("request")
            if request is None:
                raise HTTPException(status_code=500, detail="Request object not found")

            # Header or test fallback
            header_key = request.headers.get("Idempotency-Key")
            if not header_key and os.getenv("TESTING", "0") == "1":
                header_key = f"test-{key_prefix}"
            if not header_key:
                raise HTTPException(status_code=400, detail="Missing Idempotency-Key header")

            # Build robust fingerprint
            fp = await _request_fingerprint(request)

            # Final cache key
            cache_key = f"{key_prefix}::{header_key}::{fp}"

            # Serve from cache if present
            if cache_key in _idempotency_store:
                return _idempotency_store[cache_key]

            # Execute underlying function and cache result
            if inspect.iscoroutinefunction(func):
                result = await func(*args, **kwargs)
            else:
                result = func(*args, **kwargs)

            _idempotency_store[cache_key] = result
            return result

        return wrapper

    return decorator
