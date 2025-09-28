# tests/test_records_api.py


def seed_players_for_records(client):
    r = client.post(
        "/players/seed",
        json=[
            # Strong set
            {
                "symbol": "A1",
                "name": "A1",
                "is_etf": False,
                "market_cap": 2e11,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 12.0,
            },
            {
                "symbol": "A2",
                "name": "A2",
                "is_etf": False,
                "market_cap": 2e11,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 10.0,
            },
            {
                "symbol": "A3",
                "name": "A3",
                "is_etf": False,
                "market_cap": 5e9,
                "primary_bucket": "MID_CAP",
                "proj_points": 8.0,
            },
            {
                "symbol": "A4",
                "name": "A4",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 7.0,
            },
            {
                "symbol": "A5",
                "name": "A5",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 6.0,
            },
            {
                "symbol": "ETF1",
                "name": "ETF1",
                "is_etf": True,
                "market_cap": 1e11,
                "primary_bucket": "ETF",
                "proj_points": 5.0,
            },
            {
                "symbol": "A6",
                "name": "A6",
                "is_etf": False,
                "market_cap": 2e11,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 4.0,
            },
            {
                "symbol": "A7",
                "name": "A7",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 3.0,
            },
            # Medium set
            {
                "symbol": "B1",
                "name": "B1",
                "is_etf": False,
                "market_cap": 2e11,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 7.0,
            },
            {
                "symbol": "B2",
                "name": "B2",
                "is_etf": False,
                "market_cap": 5e9,
                "primary_bucket": "MID_CAP",
                "proj_points": 6.0,
            },
            {
                "symbol": "B3",
                "name": "B3",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 5.0,
            },
            {
                "symbol": "B4",
                "name": "B4",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 4.0,
            },
            {
                "symbol": "B5",
                "name": "B5",
                "is_etf": False,
                "market_cap": 1e11,
                "primary_bucket": "ETF",
                "proj_points": 3.0,
            },
            {
                "symbol": "B6",
                "name": "B6",
                "is_etf": False,
                "market_cap": 2e11,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 3.0,
            },
            {
                "symbol": "B7",
                "name": "B7",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 2.0,
            },
            {
                "symbol": "B8",
                "name": "B8",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 1.0,
            },
            # Low set
            {
                "symbol": "C1",
                "name": "C1",
                "is_etf": False,
                "market_cap": 2e11,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 2.0,
            },
            {
                "symbol": "C2",
                "name": "C2",
                "is_etf": False,
                "market_cap": 5e9,
                "primary_bucket": "MID_CAP",
                "proj_points": 2.0,
            },
            {
                "symbol": "C3",
                "name": "C3",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 2.0,
            },
            {
                "symbol": "C4",
                "name": "C4",
                "is_etf": False,
                "market_cap": 1e11,
                "primary_bucket": "ETF",
                "proj_points": 2.0,
            },
            {
                "symbol": "C5",
                "name": "C5",
                "is_etf": False,
                "market_cap": 2e11,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 1.0,
            },
            {
                "symbol": "C6",
                "name": "C6",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 1.0,
            },
            {
                "symbol": "C7",
                "name": "C7",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 0.5,
            },
            {
                "symbol": "C8",
                "name": "C8",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 0.5,
            },
        ],
    )
    assert r.status_code == 200, r.text


def draft8(client, team_id, syms):
    for s in syms:
        rr = client.post("/draft/pick", json={"team_id": team_id, "symbol": s})
        assert rr.status_code == 200, rr.text


def test_records_all(client):
    seed_players_for_records(client)

    # League + 4 teams
    r = client.post(
        "/leagues/",
        json={
            "name": "RecordsLeague",
            "roster_slots": 14,
            "starters": 8,
            "bucket_requirements": {"X": 8},
        },
    )
    assert r.status_code == 200
    league_id = r.json()["id"]

    ids = []
    for nm in ["Alpha", "Beta", "Gamma", "Delta"]:
        rr = client.post(
            f"/leagues/{league_id}/join", json={"name": nm, "owner": nm[0]}
        )
        assert rr.status_code == 200
        ids.append(rr.json()["id"])
    t_alpha, t_beta, t_gamma, t_delta = ids

    # Draft strength tiers
    draft8(client, t_alpha, ["A1", "A2", "A3", "A4", "A5", "ETF1", "A6", "A7"])
    draft8(client, t_beta, ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"])
    draft8(client, t_gamma, ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"])
    draft8(client, t_delta, ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"])

    # Single round-robin season, then score all weeks via projections stub
    assert (
        client.post(f"/schedule/season/{league_id}", params={"weeks": 0}).status_code
        == 200
    )
    assert client.post(f"/standings/{league_id}/close_season").status_code == 200

    # Records
    r = client.get(f"/records/{league_id}/all")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    for key in [
        "team_week_high",
        "game_total_high",
        "blowout_high",
        "narrowest_win",
        "longest_win_streak",
        "longest_unbeaten_streak",
    ]:
        assert key in data

    # Basic shape checks
    if data["team_week_high"] is not None:
        assert {"team_id", "team_name", "period", "points"}.issubset(
            data["team_week_high"].keys()
        )
    if data["game_total_high"] is not None:
        assert {"id", "week", "home_team_id", "away_team_id", "total_points"}.issubset(
            data["game_total_high"].keys()
        )
    if data["blowout_high"] is not None:
        assert "margin" in data["blowout_high"]
    if data["narrowest_win"] is not None:
        assert "margin" in data["narrowest_win"]
