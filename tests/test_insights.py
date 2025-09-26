# tests/test_insights.py

import re

def test_league_insights_readonly(client):
    # Seed projections
    r = client.post("/players/seed", json=[
        {"symbol": "AA", "name": "AA", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 12.0},
        {"symbol": "BB", "name": "BB", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 10.0},
        {"symbol": "CC", "name": "CC", "is_etf": False, "market_cap": 5e9,  "primary_bucket": "MID_CAP",   "proj_points": 8.0},
        {"symbol": "DD", "name": "DD", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 7.0},
        {"symbol": "EE", "name": "EE", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 6.0},
        {"symbol": "ETF1","name":"ETF1","is_etf": True,  "market_cap": 1e11, "primary_bucket": "ETF",       "proj_points": 5.0},
        {"symbol": "FX1", "name":"FX1", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 4.0},
        {"symbol": "FX2", "name":"FX2", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 3.0},
        {"symbol": "L1",  "name":"L1",  "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 1.0},
        {"symbol": "L2",  "name":"L2",  "is_etf": False, "market_cap": 1e9,  "primary_bucket": "LARGE_CAP", "proj_points": 1.0},
    ])
    assert r.status_code == 200

    # League with 3 teams
    r = client.post("/leagues/", json={"name": "Insights League", "roster_slots": 14, "starters": 8, "bucket_requirements": {"X": 8}})
    assert r.status_code == 200
    league_id = r.json()["id"]

    # Join teams
    ids = []
    for nm in ["Alpha", "Beta", "Gamma"]:
        rr = client.post(f"/leagues/{league_id}/join", json={"name": nm, "owner": nm[0]})
        assert rr.status_code == 200
        ids.append(rr.json()["id"])
    t_alpha, t_beta, t_gamma = ids

    # Draft: Alpha strong, Beta medium, Gamma weak
    for s in ["AA","BB","CC","DD","EE","ETF1","FX1","FX2"]:
        assert client.post("/draft/pick", json={"team_id": t_alpha, "symbol": s}).status_code == 200
    for s in ["AA","CC","DD","EE","ETF1","FX1","L1","L2"]:
        assert client.post("/draft/pick", json={"team_id": t_beta, "symbol": s}).status_code == 200
    for s in ["CC","DD","EE","ETF1","FX2","L1","L2"]:
        assert client.post("/draft/pick", json={"team_id": t_gamma, "symbol": s}).status_code == 200

    # Generate a season (round-robin) + close all weeks
    assert client.post(f"/schedule/season/{league_id}", params={"weeks": 0}).status_code == 200
    assert client.post(f"/standings/{league_id}/close_season").status_code == 200

    # Query insights
    r = client.get(f"/standings/{league_id}/insights")
    assert r.status_code == 200, r.text
    data = r.json()

    # Top-level keys
    for k in ["ok","league_id","pr","sos","streaks","highs"]:
        assert k in data
    assert data["ok"] is True and data["league_id"] == league_id

    # pr block
    assert isinstance(data["pr"], list) and len(data["pr"]) == 3
    for row in data["pr"]:
        for k in ["team_id","team_name","pf","pa","pr","rank_pr"]:
            assert k in row

    # sos block
    assert isinstance(data["sos"], list) and len(data["sos"]) == 3
    for row in data["sos"]:
        for k in ["team_id","team_name","sos","rank_sos"]:
            assert k in row

    # streaks block (format checks)
    assert isinstance(data["streaks"], list) and len(data["streaks"]) == 3
    for row in data["streaks"]:
        assert "team_id" in row and "team_name" in row and "streak" in row and "last5" in row
        assert re.fullmatch(r"(?:|W\d+|L\d+|T\d+)", row["streak"]) is not None
        assert re.fullmatch(r"\d-\d-\d", row["last5"]) is not None

    # highs block
    highs = data["highs"]
    for k in ["best_week","worst_week","biggest_blowout"]:
        assert k in highs
    if highs["best_week"]:
        for k in ["team_id","team_name","period","points"]:
            assert k in highs["best_week"]
    if highs["worst_week"]:
        for k in ["team_id","team_name","period","points"]:
            assert k in highs["worst_week"]
    if highs["biggest_blowout"]:
        for k in ["match_id","week","home_team_id","away_team_id","home_points","away_points","margin","winner_team_id"]:
            assert k in highs["biggest_blowout"]
