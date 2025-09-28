# smoke_mvp.py â€” end-to-end smoke test for Fantasy Stock League API
# Works with the MVP routes you've been hitting from PowerShell.

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict

import requests

BASE = os.environ.get("FSL_BASE", "http://127.0.0.1:8000")


# -------- helpers --------
def jprint(title: str, obj: Any) -> None:
    print(f"=== {title} ===")
    if isinstance(obj, (dict, list)):
        print(json.dumps(obj, indent=2))
    else:
        print(obj)


def request(method: str, path: str, **kwargs) -> Any:
    url = BASE + path
    r = requests.request(method, url, timeout=15, **kwargs)
    if r.status_code >= 400:
        # surface error body for quick diagnosis
        raise requests.HTTPError(
            f"{r.status_code} {r.reason} for {url}\nBody: {r.text}",
            response=r,
        )
    if r.headers.get("content-type", "").startswith("application/json"):
        return r.json()
    return r.text


def get(path: str) -> Any:
    return request("GET", path)


def post(path: str, data: Dict[str, Any] | None = None) -> Any:
    return request("POST", path, json=data or {})


def patch(path: str, data: Dict[str, Any]) -> Any:
    return request("PATCH", path, json=data)


def ensure_list(v: Any) -> list:
    """Some endpoints sometimes return {"value":[...]} or raw list. Normalize."""
    if isinstance(v, dict) and "value" in v and isinstance(v["value"], list):
        return v["value"]
    if isinstance(v, list):
        return v
    raise TypeError(f"Expected list or {{'value':[...]}} but got: {type(v).__name__}")


# -------- main flow --------
def main() -> None:
    # 0) health
    jprint("0) health", get("/health/ping"))

    # 1) create league + two teams
    print("=== 1) Create league + teams ===")
    league = post(
        "/leagues/",
        {"name": f"Roster Smoke {os.getpid()}"},
    )
    league_id = league["id"]

    alpha = post("/teams/", {"league_id": league_id, "name": "Team Alpha"})
    beta = post("/teams/", {"league_id": league_id, "name": "Team Beta"})
    alpha_id, beta_id = alpha["id"], beta["id"]
    print("league_id", league_id, "alpha_id", alpha_id, "beta_id", beta_id)

    # 2) seed players (upsert; projections later)
    print("=== 2) Seed players (upsert; projections later) ===")
    players = [
        {"symbol": "AAPL", "name": "Apple Inc.", "is_etf": False, "bucket": "LARGE_CAP"},
        {"symbol": "MSFT", "name": "Microsoft Corp.", "is_etf": False, "bucket": "LARGE_CAP"},
        {"symbol": "IJH", "name": "iShares Core MidCap", "is_etf": True, "bucket": "MID_CAP"},
        {"symbol": "IJR", "name": "iShares Core Small", "is_etf": True, "bucket": "SMALL_CAP"},
        {"symbol": "IWM", "name": "iShares Russell 2000", "is_etf": True, "bucket": "ETF"},
        {"symbol": "VB", "name": "Vanguard Small-Cap ETF", "is_etf": True, "bucket": "SMALL_CAP"},
        {"symbol": "GOOGL", "name": "Alphabet Inc.", "is_etf": False, "bucket": "LARGE_CAP"},
        {"symbol": "AMZN", "name": "Amazon.com, Inc.", "is_etf": False, "bucket": "LARGE_CAP"},
    ]
    post("/players/seed", players)

    # 3) fill Team Alpha active roster (5 primary + 3 that count toward FLEX)
    print("=== 3) Fill Team Alpha active roster (5 primary + 3 that count to FLEX) ===")
    adds_primary = [
        {"symbol": "AAPL", "bucket": "LARGE_CAP"},
        {"symbol": "MSFT", "bucket": "LARGE_CAP"},
        {"symbol": "IJH", "bucket": "MID_CAP"},
        {"symbol": "IJR", "bucket": "SMALL_CAP"},
        {"symbol": "IWM", "bucket": "ETF"},
    ]
    adds_flexish = [
        {"symbol": "VB", "bucket": "SMALL_CAP"},
        {"symbol": "GOOGL", "bucket": "LARGE_CAP"},
        {"symbol": "AMZN", "bucket": "LARGE_CAP"},
    ]
    for a in adds_primary + adds_flexish:
        post(f"/teams/{alpha_id}/roster/active", a)

    # 4) projections (upsert)
    print("=== 4) Give projections (upsert) ===")
    projections = [
        {"symbol": "AAPL", "is_etf": False, "bucket": "LARGE_CAP", "proj_points": 18.4},
        {"symbol": "MSFT", "is_etf": False, "bucket": "LARGE_CAP", "proj_points": 17.9},
        {"symbol": "IJH", "is_etf": True, "bucket": "MID_CAP", "proj_points": 12.2},
        {"symbol": "IJR", "is_etf": True, "bucket": "SMALL_CAP", "proj_points": 11.5},
        {"symbol": "IWM", "is_etf": True, "bucket": "ETF", "proj_points": 10.8},
        {"symbol": "VB", "is_etf": True, "bucket": "SMALL_CAP", "proj_points": 10.9},
        {"symbol": "GOOGL", "is_etf": False, "bucket": "LARGE_CAP", "proj_points": 16.7},
        {"symbol": "AMZN", "is_etf": False, "bucket": "LARGE_CAP", "proj_points": 16.1},
    ]
    post("/players/seed", projections)

    # 5) schedule one week (returns ISO like "2025-W39")
    print("=== 5) Generate 1 schedule week (returns ISO week key) ===")
    wk = post(f"/schedule/generate/{league_id}", {"weeks": 1})
    week_key = wk.get("week", "2025-W39")
    print("week_key", week_key)

    # 6) boxscore (numeric week=1)
    print("=== 6) Boxscore for Team Alpha (numeric week=1) ===")
    bs = get(f"/boxscore/{league_id}/1/{alpha_id}")
    jprint(
        "",
        {
            "primary_points": round(bs["totals"]["primary_points"], 1),
            "flex_points": round(bs["totals"]["flex_points"], 1),
            "grand_total": round(bs["totals"]["grand_total"], 1),
        },
    )

    # 7) close scoring week (ISO week key)
    print("=== 7) Close scoring week (uses ISO key) ===")
    closed = post(f"/scoring/close_week/{league_id}", {"week": week_key})
    jprint("", closed)

    # 8) standings
    print("=== 8) Standings ===")
    snapshot = get(f"/standings/{league_id}/snapshot")
    history = get(f"/standings/{league_id}/history")
    table = get(f"/standings/{league_id}/table")

    snap_rows = ensure_list(snapshot)
    hist_rows = ensure_list(history)
    table_rows = ensure_list(table)

    print("\n-- snapshot --\n")
    print(json.dumps(snap_rows, indent=2))
    print("\n-- history --\n")
    print(json.dumps(hist_rows, indent=2))
    print("\n-- table --\n")
    print(json.dumps(table_rows, indent=2))

    # 9) quick assertions (fail fast in CI if scoring/standings regress)
    alpha_row = next(r for r in table_rows if r.get("team_name") == "Team Alpha")
    beta_row = next(r for r in table_rows if r.get("team_name") == "Team Beta")
    assert round(alpha_row["points_for"], 1) == 114.5, "Alpha points_for mismatch"
    assert round(beta_row["points_for"], 1) == 0.0, "Beta points_for mismatch"
    assert alpha_row["wins"] == 1 and beta_row["wins"] == 0, "Win/Loss mismatch"

    # 10) optional extra endpoints (don't fail the smoke if absent)
    print("\n=== extras (optional) ===")

    def try_print(title: str, fn, *args, **kwargs):
        try:
            jprint(title, fn(*args, **kwargs))
        except Exception as e:
            print(f"{title}: not available ({e})")

    try_print("tiebreakers", get, f"/standings/{league_id}/tiebreakers")
    try_print("power_rankings", get, f"/standings/{league_id}/power_rankings")
    try_print("elo", get, f"/standings/{league_id}/elo")
    try_print("insights", get, f"/standings/{league_id}/insights")
    try_print("season schedule (POST)", post, f"/schedule/season/{league_id}", {})

    # 11) dump result files (handy for diffing locally)
    out = Path("smoke_out")
    out.mkdir(exist_ok=True)
    (out / "snapshot.json").write_text(json.dumps(snap_rows, indent=2))
    (out / "history.json").write_text(json.dumps(hist_rows, indent=2))
    (out / "table.json").write_text(json.dumps(table_rows, indent=2))

    print("\nsmoke_mvp.py passed.")


if __name__ == "__main__":
    main()
