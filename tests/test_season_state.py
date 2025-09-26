# tests/test_season_state.py

def seed_minimal_players(client):
    r = client.post("/players/seed", json=[
        {"symbol": "A1", "name": "A1", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 12.0},
        {"symbol": "A2", "name": "A2", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 10.0},
        {"symbol": "A3", "name": "A3", "is_etf": False, "market_cap": 5e9,  "primary_bucket": "MID_CAP",   "proj_points": 8.0},
        {"symbol": "A4", "name": "A4", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 7.0},
        {"symbol": "A5", "name": "A5", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 6.0},
        {"symbol": "ETF1","name":"ETF1","is_etf": True,  "market_cap": 1e11, "primary_bucket": "ETF",       "proj_points": 5.0},
        {"symbol": "A6", "name":"A6",  "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 4.0},
        {"symbol": "A7", "name":"A7",  "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 3.0},
        {"symbol": "L1", "name":"L1",  "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 1.0},
        {"symbol": "L2", "name":"L2",  "is_etf": False, "market_cap": 1e9,  "primary_bucket": "LARGE_CAP", "proj_points": 1.0},
    ])
    assert r.status_code == 200


def test_season_state_transitions(client):
    seed_minimal_players(client)

    # League + 4 teams
    r = client.post("/leagues/", json={"name": "StateFlow", "roster_slots": 14, "starters": 8, "bucket_requirements": {"X": 8}})
    assert r.status_code == 200
    league_id = r.json()["id"]

    ids = []
    for nm in ["Alpha", "Beta", "Gamma", "Delta"]:
        rr = client.post(f"/leagues/{league_id}/join", json={"name": nm, "owner": nm[0]})
        assert rr.status_code == 200
        ids.append(rr.json()["id"])

    # Simple drafts (not critical to state transitions)
    pools = [
        ["A1","A2","A3","A4","A5","ETF1","A6","A7"],
        ["A1","A3","A4","A5","ETF1","A6","A7","L1"],
        ["A1","A3","A4","A5","ETF1","A7","L1","L2"],
        ["A3","A4","A5","ETF1","A7","L1","L2","A2"],
    ]
    for tid, syms in zip(ids, pools):
        for s in syms:
            assert client.post("/draft/pick", json={"team_id": tid, "symbol": s}).status_code == 200

    # Generate full season and score all regular-season weeks
    assert client.post(f"/schedule/season/{league_id}", params={"weeks": 0}).status_code == 200
    assert client.post(f"/standings/{league_id}/close_season").status_code == 200

    # State: regular (no semis yet)
    r = client.get(f"/season/{league_id}/state"); assert r.status_code == 200
    assert r.json()["state"] == "regular"

    # Generate semis
    r = client.post(f"/season/{league_id}/advance"); assert r.status_code == 200
    r = client.get(f"/season/{league_id}/state"); assert r.status_code == 200
    assert r.json()["state"] == "semis"

    # Score semis
    r = client.post(f"/season/{league_id}/advance"); assert r.status_code == 200
    r = client.get(f"/season/{league_id}/state"); assert r.status_code == 200
    # After scoring semis, finals not generated yet => still semis
    assert r.json()["state"] == "semis"

    # Generate finals (and bronze)
    r = client.post(f"/season/{league_id}/advance"); assert r.status_code == 200
    r = client.get(f"/season/{league_id}/state"); assert r.status_code == 200
    assert r.json()["state"] == "finals"

    # Score bronze (first)
    r = client.post(f"/season/{league_id}/advance"); assert r.status_code == 200
    r = client.get(f"/season/{league_id}/state"); assert r.status_code == 200
    assert r.json()["state"] == "finals"

    # Score finals (may take 1–2 calls depending on ordering)
    # Loop until we reach complete
    for _ in range(3):
        r = client.post(f"/season/{league_id}/advance"); assert r.status_code == 200
        s = client.get(f"/season/{league_id}/state"); assert s.status_code == 200
        if s.json()["state"] == "complete":
            break
    else:
        assert False, "Did not reach complete state"
