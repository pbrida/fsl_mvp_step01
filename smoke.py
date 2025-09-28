# smoke.py — end-to-end test runner for Fantasy Stock League API
import requests
import json

BASE = "http://127.0.0.1:8000"


def post(path, data):
    r = requests.post(BASE + path, json=data)
    r.raise_for_status()
    return r.json()


def patch(path, data):
    r = requests.patch(BASE + path, json=data)
    r.raise_for_status()
    return r.json()


def get(path):
    r = requests.get(BASE + path)
    r.raise_for_status()
    return r.json()


print("=== 1) create league ===")
league = post(
    "/leagues/",
    {
        "name": "Alpha League",
        "roster_slots": 14,
        "starters": 8,
        "bucket_requirements": {
            "LARGE_CAP": 1,
            "MID_CAP": 1,
            "SMALL_CAP": 1,
            "ETF": 1,
            "DIVIDEND": 1,
            "TECH": 1,
            "INTERNATIONAL": 1,
            "WILDCARD": 1,
        },
    },
)
league_id = league["id"]
print("league_id", league_id)

print("=== 2) join teams ===")
team1 = post(f"/leagues/{league_id}/join", {"name": "Bulls", "owner": "Alice"})
team2 = post(f"/leagues/{league_id}/join", {"name": "Bears", "owner": "Bob"})
t1, t2 = team1["id"], team2["id"]
print("team ids", t1, t2)

print("=== 3) draft ===")
t1_syms = ["AAPL", "MSFT", "VTI", "KO", "NVDA", "SHEL", "SHOP", "TSLA"]
t2_syms = ["GOOGL", "AMZN", "VOO", "PG", "META", "BABA", "ADBE", "NFLX"]
for s in t1_syms:
    post("/draft/pick", {"team_id": t1, "symbol": s})
for s in t2_syms:
    post("/draft/pick", {"team_id": t2, "symbol": s})

print("=== 4) rosters ===")
r1 = get(f"/draft/roster/{t1}")
r2 = get(f"/draft/roster/{t2}")


def slot_id_by_symbol(roster, sym):
    for row in roster:
        if row["symbol"].upper() == sym.upper():
            return row["id"]
    raise RuntimeError(f"slot not found for {sym}")


print("=== 5) buckets ===")
map1 = {
    "AAPL": "TECH",
    "MSFT": "MID_CAP",
    "VTI": "ETF",
    "KO": "DIVIDEND",
    "NVDA": "WILDCARD",
    "SHEL": "INTERNATIONAL",
    "SHOP": "SMALL_CAP",
    "TSLA": "LARGE_CAP",
}
map2 = {
    "GOOGL": "TECH",
    "AMZN": "MID_CAP",
    "VOO": "ETF",
    "PG": "DIVIDEND",
    "META": "WILDCARD",
    "BABA": "INTERNATIONAL",
    "ADBE": "SMALL_CAP",
    "NFLX": "LARGE_CAP",
}
chosen1 = []
for sym, bucket in map1.items():
    sid = slot_id_by_symbol(r1, sym)
    chosen1.append(sid)
    patch(f"/draft/slot/{sid}/bucket", {"bucket": bucket})
chosen2 = []
for sym, bucket in map2.items():
    sid = slot_id_by_symbol(r2, sym)
    chosen2.append(sid)
    patch(f"/draft/slot/{sid}/bucket", {"bucket": bucket})

print("chosen1", chosen1)
print("chosen2", chosen2)

print("=== 6) set lineups ===")
post("/lineup/set", {"team_id": t1, "slot_ids": chosen1})
post("/lineup/set", {"team_id": t2, "slot_ids": chosen2})

print("=== 7) schedule & close week ===")
post(f"/schedule/generate/{league_id}", {})
post(f"/standings/{league_id}/close_week", {})

print("=== 8) outputs ===")
standings = get(f"/standings/{league_id}?persist=true")
history = get(f"/standings/{league_id}/history")
table = get(f"/standings/{league_id}/table")

print("\n-- standings --\n", json.dumps(standings, indent=2))
print("\n-- history --\n", json.dumps(history, indent=2))
print("\n-- table --\n", json.dumps(table, indent=2))
