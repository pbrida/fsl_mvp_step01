# fantasy_stocks/main.py
from __future__ import annotations

import json
import logging
import os
import time
import uuid

from fastapi import FastAPI, Request

from fantasy_stocks import models  # noqa: F401  (import registers models with Base)

# --- DB bootstrapping: create tables at startup ---
from fantasy_stocks.db import Base, engine

# Routers
from .routers import (
    analytics,
    awards,
    boxscore,
    draft,
    free_agency,
    league,
    lineup,
    players,
    playoffs,
    prices,
    records,
    schedule,
    scoring,
    season,
    standings,
    standings_snapshot,
    teams,
)

# ---------- App ----------
app = FastAPI(title="Fantasy Stocks MVP", version="0.1.0")


# Create tables once on app start
@app.on_event("startup")
def _create_tables() -> None:
    Base.metadata.create_all(bind=engine)


# ---------- Minimal structured logging ----------
logging.basicConfig(level=getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO))
logger = logging.getLogger("fantasy_stocks")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    response = await call_next(request)
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
        pass
    return response


# ---------- Health ----------
@app.get("/health/ping")
def ping():
    return {"ok": True, "ping": "pong"}


def _include_router_flex(app: FastAPI, module) -> None:
    for attr in ("router", "route"):
        if hasattr(module, attr):
            app.include_router(getattr(module, attr))
            return
    name = getattr(module, "__name__", str(module))
    raise RuntimeError(f"Module {name} does not define `router` or `route`")


# ---------- Include Routers ----------
_include_router_flex(app, league)  # /leagues
_include_router_flex(app, draft)  # /draft
_include_router_flex(app, lineup)  # /lineup
_include_router_flex(app, standings)  # /standings
_include_router_flex(app, schedule)  # /schedule
_include_router_flex(app, free_agency)  # /free-agency
_include_router_flex(app, players)  # /players
_include_router_flex(app, teams)  # /teams
_include_router_flex(app, scoring)  # /scoring
_include_router_flex(app, standings_snapshot)  # /standings-snapshot
_include_router_flex(app, boxscore)  # /boxscore
_include_router_flex(app, prices)  # /prices
_include_router_flex(app, playoffs)  # /playoffs
_include_router_flex(app, season)  # /season
_include_router_flex(app, awards)  # /awards
_include_router_flex(app, records)  # /records
_include_router_flex(app, analytics)  # /analytics
