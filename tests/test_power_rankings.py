# tests/test_power_rankings.py

def test_power_rankings_order_matches_pf_pa(client):
    # Seed simple catalog with projection points
    r = client.post("/players/seed", json=[
        {"symbol": "AAA", "name": "AAA", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 12.0},
        {"symbol": "BBB", "name": "BBB", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 10.0},
        {"symbol": "CCC", "name": "CCC", "is_etf": False, "market_cap": 5e9,  "primary_bucket": "MID_CAP",   "proj_points": 8.0},
        {"symbol": "DDD", "name": "DDD", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 7.0},
        {"symbol": "EEE", "name": "EEE", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 6.0},
        {"symbol": "ETF1","name":"ETF1","is_etf": True,  "market_cap": 1e11, "primary_bucket": "ETF",       "proj_points": 5.0},
        {"symbol": "FX1", "name":"FX1", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 4.0},
        {"symbol": "FX2", "name":"FX2", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 3.0},
        # Low scorers for Team Beta to ensure PF/PA separation
        {"symbol": "ZZ1", "name":"ZZ1", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 0.5},
        {"symbol": "ZZ2", "name":"ZZ2", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "LARGE_CAP", "proj_points": 0.5},
    ])
    assert r.status_code == 200, r.text

    # League + 2 teams
    r = client.post("/leagues/", json={"name": "PR League", "roster_slots": 14, "starters": 8, "bucket_requirements": {"X": 8}})
    assert r.status_code == 200
    league_id = r.json()["id"]

    r = client.post(f"/leagues/{league_id}/join", json={"name": "Alpha", "owner": "A"}); assert r.status_code == 200
    t1 = r.json()["id"]
    r = client.post(f"/leagues/{league_id}/join", json={"name": "Beta",  "owner": "B"}); assert r.status_code == 200
    t2 = r.json()["id"]

    # Draft 8 for Alpha (strong)
    for s in ["AAA","BBB","CCC","DDD","EEE","ETF1","FX1","FX2"]:
        rr = client.post("/draft/pick", json={"team_id": t1, "symbol": s}); assert rr.status_code == 200

    # Draft 8 for Beta (weaker)
    for s in ["AAA","ZZ1","ZZ2","CCC","DDD","EEE","ETF1","FX2"]:
        rr = client.post("/draft/pick", json={"team_id": t2, "symbol": s}); assert rr.status_code == 200

    # Schedule + score using scoring router (works without setting lineups)
    r = client.post(f"/schedule/generate/{league_id}", json={}); assert r.status_code == 200
    r = client.post(f"/scoring/close_week/{league_id}");         assert r.status_code == 200

    # Power rankings
    r = client.get(f"/standings/{league_id}/power_rankings")
    assert r.status_code == 200, r.text
    rows = r.json()
    assert isinstance(rows, list) and len(rows) == 2

    # Fields present
    for row in rows:
        for k in ["team_id", "team_name", "pf", "pa", "pr"]:
            assert k in row

    # Alpha should rank above Beta by PR (higher PF, lower PA)
    assert rows[0]["team_name"] == "Alpha"
    assert rows[0]["pr"] >= rows[1]["pr"]
    assert rows[0]["pf"] > rows[1]["pf"] or rows[0]["pa"] < rows[1]["pa"]
