# tests/test_awards_season.py

def seed_players_awards(client):
    r = client.post("/players/seed", json=[
        {"symbol": "A1", "name": "A1", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 12.0},
        {"symbol": "A2", "name": "A2", "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 10.0},
        {"symbol": "A3", "name": "A3", "is_etf": False, "market_cap": 5e9,  "primary_bucket": "MID_CAP",   "proj_points": 8.0},
        {"symbol": "A4", "name": "A4", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 7.0},
        {"symbol": "A5", "name": "A5", "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 6.0},
        {"symbol": "ETF1","name":"ETF1","is_etf": True,  "market_cap": 1e11, "primary_bucket": "ETF",       "proj_points": 5.0},
        {"symbol": "A6", "name":"A6",  "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 4.0},
        {"symbol": "A7", "name":"A7",  "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 3.0},
        {"symbol": "B1", "name":"B1",  "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 7.0},
        {"symbol": "B2", "name":"B2",  "is_etf": False, "market_cap": 5e9,  "primary_bucket": "MID_CAP",   "proj_points": 6.0},
        {"symbol": "B3", "name":"B3",  "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 5.0},
        {"symbol": "B4", "name":"B4",  "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 4.0},
        {"symbol": "B5", "name":"B5",  "is_etf": False, "market_cap": 1e11, "primary_bucket": "ETF",       "proj_points": 3.0},
        {"symbol": "B6", "name":"B6",  "is_etf": False, "market_cap": 2e11, "primary_bucket": "LARGE_CAP", "proj_points": 3.0},
        {"symbol": "B7", "name":"B7",  "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 2.0},
        {"symbol": "B8", "name":"B8",  "is_etf": False, "market_cap": 1e9,  "primary_bucket": "SMALL_CAP", "proj_points": 1.0},
    ])
    assert r.status_code == 200, r.text


def draft8(client, team_id, syms):
    for s in syms:
        rr = client.post("/draft/pick", json={"team_id": team_id, "symbol": s})
        assert rr.status_code == 200, rr.text


def test_awards_season(client):
    seed_players_awards(client)

    r = client.post("/leagues/", json={"name": "AwardsSeason", "roster_slots": 14, "starters": 8, "bucket_requirements": {"X": 8}})
    assert r.status_code == 200
    league_id = r.json()["id"]

    ids = []
    for nm in ["Alpha", "Beta", "Gamma", "Delta"]:
        rr = client.post(f"/leagues/{league_id}/join", json={"name": nm, "owner": nm[0]})
        assert rr.status_code == 200
        ids.append(rr.json()["id"])
    t_alpha, t_beta, t_gamma, t_delta = ids

    draft8(client, t_alpha, ["A1","A2","A3","A4","A5","ETF1","A6","A7"])
    draft8(client, t_beta,  ["B1","B2","B3","B4","B5","B6","B7","B8"])
    draft8(client, t_gamma, ["B1","B2","B3","B4","B5","B6","B7","B8"])
    draft8(client, t_delta, ["B1","B2","B3","B4","B5","B6","B7","B8"])

    assert client.post(f"/schedule/season/{league_id}", params={"weeks": 0}).status_code == 200
    assert client.post(f"/standings/{league_id}/close_season").status_code == 200

    r = client.get(f"/awards/{league_id}/season")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    for key in [
        "winningest_team",
        "mvp_offense",
        "best_defense",
        "highest_single_week_team",
        "highest_scoring_game",
        "biggest_blowout",
    ]:
        assert key in data
