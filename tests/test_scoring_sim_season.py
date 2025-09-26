def test_simulate_season_runs_all_weeks(client):
    # Seed a minimal universe with proj_points so both teams have non-zero scores
    r = client.post("/players/seed", json=[
        {"symbol": "AA", "name": "AA", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 12.0},
        {"symbol": "BB", "name": "BB", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 10.0},
        {"symbol": "CC", "name": "CC", "is_etf": False, "market_cap": 5e9,  "primary_bucket": "MID_CAP",   "proj_points": 8.0},
        {"symbol": "DD", "name": "DD", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 7.0},
        {"symbol": "EE", "name": "EE", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 6.0},
        {"symbol": "ETF1","name":"ETF1","is_etf": True, "market_cap": 1e11, "primary_bucket": "ETF",       "proj_points": 5.0},
        {"symbol": "FX1","name":"FX1", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 4.0},
        {"symbol": "FX2","name":"FX2", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 3.0},
    ])
    assert r.status_code == 200

    # League + 4 teams to create multi-week schedule
    r = client.post("/leagues/", json={"name": "Sim Szn", "roster_slots": 14, "starters": 8, "bucket_requirements": {"X": 8}})
    assert r.status_code == 200
    league_id = r.json()["id"]

    team_ids = []
    for nm in ["T1","T2","T3","T4"]:
        r = client.post(f"/leagues/{league_id}/join", json={"name": nm, "owner": nm})
        assert r.status_code == 200
        team_ids.append(r.json()["id"])

    # Give each team the same 8 starters quickly
    starters = ["AA","BB","CC","DD","EE","ETF1","FX1","FX2"]
    for tid in team_ids:
        for s in starters:
            rr = client.post("/draft/pick", json={"team_id": tid, "symbol": s})
            assert rr.status_code == 200, rr.text

    # Generate schedule (multiple weeks for 4 teams)
    r = client.post(f"/schedule/generate/{league_id}", json={})
    assert r.status_code == 200, r.text

    # Simulate full season (closes all open weeks)
    r = client.post(f"/scoring/simulate_season/{league_id}")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    # Should close at least 1 week (depends on schedule length)
    assert len(data["closed_weeks"]) >= 1
