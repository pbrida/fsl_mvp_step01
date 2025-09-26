# fantasy_stocks/main.py
from __future__ import annotations

import json
import logging
import os
import time
import uuid

from fastapi import FastAPI, Request

# Import router modules (not the variables inside; we'll detect attr names below)
from .routers import league
from .routers import draft
from .routers import lineup
from .routers import standings
from .routers import schedule
from .routers import free_agency
from .routers import players
from .routers import teams
from .routers import scoring
from .routers import standings_snapshot
from .routers import boxscore
from .routers import prices
from .routers import playoffs
from .routers import season
from .routers import awards
from .routers import records
from .routers import analytics


# ---------- App ----------
app = FastAPI(title="Fantasy Stocks MVP", version="0.1.0")

# ---------- Minimal structured logging ----------
# Configure once; JSON-per-line so logs are ingestion-friendly.
logging.basicConfig(level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO))
logger = logging.getLogger("fantasy_stocks")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Add/propagate X-Request-ID and log method/path/status/duration/idempotency-key.
    Emits a single JSON log line per request (on completion).
    """
    start = time.perf_counter()

    # Propagate request id if the client sent one; else generate a new one.
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())

    # Let the request proceed.
    response = await call_next(request)

    # Always return the request id so clients can correlate.
    response.headers["X-Request-ID"] = request_id

    duration_ms = (time.perf_counter() - start) * 1000.0
    try:
        log_obj = {
            "msg": "request",
            "request_id": request_id,
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": round(duration_ms, 2),
            "idempotency_key": request.headers.get("Idempotency-Key") or None,
        }
        logger.info(json.dumps(log_obj, separators=(",", ":")))
    except Exception:
        # Never fail a request due to logging; swallow any logging errors.
        pass

    return response


# ---------- Health ----------
@app.get("/health/ping")
def ping():
    return {"ok": True, "ping": "pong"}


def _include_router_flex(app: FastAPI, module) -> None:
    """
    Include a router from a module that may expose `router` or `route`.
    Raises a clear error if neither is present.
    """
    for attr in ("router", "route"):
        if hasattr(module, attr):
            app.include_router(getattr(module, attr))
            return
    name = getattr(module, "__name__", str(module))
    raise RuntimeError(f"Module {name} does not define `router` or `route`")


# ---------- Include Routers (accepts either `router` or `route`) ----------
_include_router_flex(app, league)              # /leagues
_include_router_flex(app, draft)               # /draft
_include_router_flex(app, lineup)              # /lineup
_include_router_flex(app, standings)           # /standings
_include_router_flex(app, schedule)            # /schedule
_include_router_flex(app, free_agency)         # /free-agency
_include_router_flex(app, players)             # /players
_include_router_flex(app, teams)               # /teams
_include_router_flex(app, scoring)             # /scoring
_include_router_flex(app, standings_snapshot)  # /standings-snapshot
_include_router_flex(app, boxscore)            # /boxscore
_include_router_flex(app, prices)              # /prices
_include_router_flex(app, playoffs)            # /playoffs
_include_router_flex(app, season)              # /season
_include_router_flex(app, awards)              # /awards
_include_router_flex(app, records)             # /records
_include_router_flex(app, analytics)           # /analytics
