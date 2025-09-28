# tests/test_e2e.py
def test_end_to_end_flow(client):
    # 1) create league  (server ignores custom bucket settings now; fixed rules are enforced)
    league_body = {
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
    }
    r = client.post("/leagues/", json=league_body)
    assert r.status_code == 200, r.text
    league = r.json()
    league_id = league["id"]

    # 2) join two teams
    r = client.post(f"/leagues/{league_id}/join", json={"name": "Bulls", "owner": "Alice"})
    assert r.status_code == 200, r.text
    t1 = r.json()["id"]

    r = client.post(f"/leagues/{league_id}/join", json={"name": "Bears", "owner": "Bob"})
    assert r.status_code == 200, r.text
    t2 = r.json()["id"]

    # 3) draft picks (8 each)
    team1_syms = ["AAPL", "MSFT", "VTI", "KO", "NVDA", "SHEL", "SHOP", "TSLA"]
    team2_syms = ["GOOGL", "AMZN", "VOO", "PG", "META", "BABA", "ADBE", "NFLX"]
    for s in team1_syms:
        r = client.post("/draft/pick", json={"team_id": t1, "symbol": s})
        assert r.status_code == 200, r.text
    for s in team2_syms:
        r = client.post("/draft/pick", json={"team_id": t2, "symbol": s})
        assert r.status_code == 200, r.text

    # 4) fetch rosters
    r1 = client.get(f"/draft/roster/{t1}").json()
    r2 = client.get(f"/draft/roster/{t2}").json()

    def slot_id_by_symbol(roster, sym: str) -> int:
        for row in roster:
            if row["symbol"].upper() == sym.upper():
                return row["id"]
        raise AssertionError(f"slot not found for {sym}")

    # 5) set buckets for 8 starters (aligned with fixed rules)
    # Team 1: 2 LARGE_CAP, 1 MID_CAP, 2 SMALL_CAP, 1 ETF, 2 FLEX
    map1 = {
        # LARGE_CAP (2)
        "AAPL": "LARGE_CAP",
        "TSLA": "LARGE_CAP",
        # MID_CAP (1)
        "MSFT": "MID_CAP",  # for test purposes
        # SMALL_CAP (2)
        "SHOP": "SMALL_CAP",
        "KO": "SMALL_CAP",
        # ETF (1)
        "VTI": "ETF",
        # FLEX (2) — any eligible bucket is fine; we tag as FLEX to satisfy current validator
        "NVDA": "FLEX",
        "SHEL": "FLEX",
    }

    # Team 2: 2 LARGE_CAP, 1 MID_CAP, 2 SMALL_CAP, 1 ETF, 2 FLEX
    map2 = {
        # LARGE_CAP (2)
        "GOOGL": "LARGE_CAP",
        "AMZN": "LARGE_CAP",
        # MID_CAP (1)
        "META": "MID_CAP",
        # SMALL_CAP (2)
        "ADBE": "SMALL_CAP",
        "PG": "SMALL_CAP",
        # ETF (1)
        "VOO": "ETF",
        # FLEX (2)
        "BABA": "FLEX",
        "NFLX": "FLEX",
    }

    chosen1, chosen2 = [], []
    for sym, bucket in map1.items():
        sid = slot_id_by_symbol(r1, sym)
        chosen1.append(sid)
        r = client.patch(f"/draft/slot/{sid}/bucket", json={"bucket": bucket})
        assert r.status_code == 200, r.text
    for sym, bucket in map2.items():
        sid = slot_id_by_symbol(r2, sym)
        chosen2.append(sid)
        r = client.patch(f"/draft/slot/{sid}/bucket", json={"bucket": bucket})
        assert r.status_code == 200, r.text

    # 6) set lineups (activate exactly 8)
    r = client.post("/lineup/set", json={"team_id": t1, "slot_ids": chosen1})
    assert r.status_code == 200, r.text
    r = client.post("/lineup/set", json={"team_id": t2, "slot_ids": chosen2})
    assert r.status_code == 200, r.text

    # 7) generate schedule & close week
    r = client.post(f"/schedule/generate/{league_id}", json={})
    assert r.status_code == 200, r.text
    r = client.post(f"/standings/{league_id}/close_week", headers={"Idempotency-Key": "test-key"})

    assert r.status_code == 200, r.text

    # 8) verify outputs
    stand = client.get(f"/standings/{league_id}?persist=true")
    assert stand.status_code == 200, stand.text
    data = stand.json()
    # Expect two teams with numeric points
    assert len(data) == 2
    assert all(isinstance(x["points"], (int, float)) for x in data)

    hist = client.get(f"/standings/{league_id}/history")
    assert hist.status_code == 200, hist.text
    assert len(hist.json()) == 2

    table = client.get(f"/standings/{league_id}/table")
    assert table.status_code == 200, table.text
    tbl = table.json()
    assert len(tbl) == 2
    # team fields present
    for row in tbl:
        for k in [
            "team_id",
            "team_name",
            "wins",
            "losses",
            "ties",
            "games_played",
            "points_for",
            "points_against",
            "point_diff",
            "win_pct",
        ]:
            assert k in row
