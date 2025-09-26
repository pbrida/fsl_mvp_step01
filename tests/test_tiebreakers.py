# tests/test_tiebreakers.py

def test_tiebreakers_orders_by_rules(client):
    # Seed projections
    r = client.post("/players/seed", json=[
        {"symbol": "A1", "name": "A1", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 12.0},
        {"symbol": "A2", "name": "A2", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 10.0},
        {"symbol": "A3", "name": "A3", "is_etf": False, "market_cap": 5e9,  "primary_bucket": "MID_CAP",   "proj_points": 8.0},
        {"symbol": "A4", "name": "A4", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 7.0},
        {"symbol": "A5", "name": "A5", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 6.0},
        {"symbol": "ETF1","name":"ETF1","is_etf": True,  "market_cap": 1e11, "primary_bucket": "ETF",       "proj_points": 5.0},
        {"symbol": "A6", "name":"A6",  "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 4.0},
        {"symbol": "A7", "name":"A7",  "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 3.0},
        # Beta lower
        {"symbol": "B1", "name":"B1",  "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 1.0},
        {"symbol": "B2", "name":"B2",  "is_etf": False, "market_cap": 1e9,  "primary_bucket": "LARGE_CAP", "proj_points": 1.0},
    ])
    assert r.status_code == 200

    # League + 2 teams
    r = client.post("/leagues/", json={"name": "TB League", "roster_slots": 14, "starters": 8, "bucket_requirements": {"X": 8}})
    assert r.status_code == 200
    league_id = r.json()["id"]

    r = client.post(f"/leagues/{league_id}/join", json={"name": "Alpha", "owner": "A"}); assert r.status_code == 200
    t1 = r.json()["id"]
    r = client.post(f"/leagues/{league_id}/join", json={"name": "Beta",  "owner": "B"}); assert r.status_code == 200
    t2 = r.json()["id"]

    # Draft 8 for Alpha (strong)
    for s in ["A1","A2","A3","A4","A5","ETF1","A6","A7"]:
        rr = client.post("/draft/pick", json={"team_id": t1, "symbol": s}); assert rr.status_code == 200

    # Draft 8 for Beta (weaker)
    for s in ["A1","B1","B2","A3","A4","A5","ETF1","A7"]:
        rr = client.post("/draft/pick", json={"team_id": t2, "symbol": s}); assert rr.status_code == 200

    # Schedule + score (uses scoring router so we don't need to manage lineups)
    r = client.post(f"/schedule/generate/{league_id}", json={}); assert r.status_code == 200
    r = client.post(f"/scoring/close_week/{league_id}");         assert r.status_code == 200

    # Tiebreakers for both teams
    r = client.get(f"/standings/{league_id}/tiebreakers")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list) and len(rows) == 2

    # Alpha should be first
    assert rows[0]["team_name"] == "Alpha"
    # Fields present
    for row in rows:
        for k in ["team_id", "team_name", "win_pct", "h2h_win_pct", "point_diff", "points_for", "reason"]:
            assert k in row

    # Subset request with team_ids filter also works
    r = client.get(f"/standings/{league_id}/tiebreakers", params={"team_ids": f"{t2},{t1}"})
    assert r.status_code == 200
    subset = r.json()
    assert len(subset) == 2 and subset[0]["team_name"] == "Alpha"
