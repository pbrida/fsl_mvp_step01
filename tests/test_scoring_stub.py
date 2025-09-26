# tests/test_scoring_stub.py

def test_scoring_close_week_uses_proj_points(client):
    # Seed a full 8-starter set for two teams.
    # Team A totals 80 (8 x 10); Team B totals 40 (8 x 5)
    seed = [
        # Team A primaries
        {"symbol": "L1", "name": "Large1", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 10.0},
        {"symbol": "L2", "name": "Large2", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 10.0},
        {"symbol": "M1", "name": "Mid1",   "is_etf": False, "market_cap": 5e9,  "primary_bucket": "MID_CAP",   "proj_points": 10.0},
        {"symbol": "S1", "name": "Small1", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 10.0},
        {"symbol": "S2", "name": "Small2", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 10.0},
        {"symbol": "E1", "name": "ETF1",   "is_etf": True,  "market_cap": 1e11, "primary_bucket": "ETF",       "proj_points": 10.0},
        # Team A surplus → FLEX (any primary bucket)
        {"symbol": "F1", "name": "Flex1",  "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 10.0},
        {"symbol": "F2", "name": "Flex2",  "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 10.0},

        # Team B primaries
        {"symbol": "L3", "name": "Large3", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 5.0},
        {"symbol": "L4", "name": "Large4", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 5.0},
        {"symbol": "M2", "name": "Mid2",   "is_etf": False, "market_cap": 5e9,  "primary_bucket": "MID_CAP",   "proj_points": 5.0},
        {"symbol": "S3", "name": "Small3", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 5.0},
        {"symbol": "S4", "name": "Small4", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 5.0},
        {"symbol": "E2", "name": "ETF2",   "is_etf": True,  "market_cap": 1e11, "primary_bucket": "ETF",       "proj_points": 5.0},
        # Team B surplus → FLEX
        {"symbol": "F3", "name": "Flex3",  "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 5.0},
        {"symbol": "F4", "name": "Flex4",  "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 5.0},
    ]
    r = client.post("/players/seed", json=seed)
    assert r.status_code == 200, r.text

    # League + two teams
    r = client.post("/leagues/", json={"name": "Scoring League", "roster_slots": 14, "starters": 8, "bucket_requirements": {"X": 8}})
    assert r.status_code == 200
    league_id = r.json()["id"]

    r = client.post(f"/leagues/{league_id}/join", json={"name": "TeamA", "owner": "A"})
    assert r.status_code == 200
    t1 = r.json()["id"]

    r = client.post(f"/leagues/{league_id}/join", json={"name": "TeamB", "owner": "B"})
    assert r.status_code == 200
    t2 = r.json()["id"]

    # Draft 8 starters each (auto-placed: primaries then FLEX)
    team_a_syms = ["L1","L2","M1","S1","S2","E1","F1","F2"]  # 8 x 10 = 80
    team_b_syms = ["L3","L4","M2","S3","S4","E2","F3","F4"]  # 8 x 5  = 40
    for s in team_a_syms:
        rr = client.post("/draft/pick", json={"team_id": t1, "symbol": s})
        assert rr.status_code == 200, rr.text
    for s in team_b_syms:
        rr = client.post("/draft/pick", json={"team_id": t2, "symbol": s})
        assert rr.status_code == 200, rr.text

    # Generate one week of schedule (1 match with 2 teams)
    r = client.post(f"/schedule/generate/{league_id}", json={})
    assert r.status_code == 200, r.text

    # Close the week using scoring stub (proj_points)
    r = client.post(f"/scoring/close_week/{league_id}")
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["ok"] is True
    assert result["matches_scored"] >= 1

    # Totals should match sums of proj_points across ACTIVE starters
    totals = result["totals"]
    assert abs(totals[str(t1)] - 80.0) < 1e-6 or abs(totals.get(t1, 0.0) - 80.0) < 1e-6
    assert abs(totals[str(t2)] - 40.0) < 1e-6 or abs(totals.get(t2, 0.0) - 40.0) < 1e-6
