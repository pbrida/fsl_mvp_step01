# tests/test_elo_rankings.py


def seed_players_for_elo(client):
    # Higher totals for Alpha; medium for Beta; low for Gamma
    r = client.post(
        "/players/seed",
        json=[
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


def activate8(client, team_id):
    roster = client.get(f"/draft/roster/{team_id}").json()
    slot_ids = [r["id"] for r in roster][:8]
    resp = client.post("/lineup/set", json={"team_id": team_id, "slot_ids": slot_ids})
    assert resp.status_code == 200, resp.text


def test_elo_rankings_flow(client):
    seed_players_for_elo(client)

    # League + 3 teams
    r = client.post(
        "/leagues/",
        json={
            "name": "EloLeague",
            "roster_slots": 14,
            "starters": 8,
            "bucket_requirements": {"X": 8},
        },
    )
    assert r.status_code == 200
    league_id = r.json()["id"]

    rr = client.post(f"/leagues/{league_id}/join", json={"name": "Alpha", "owner": "A"})
    assert rr.status_code == 200
    t_alpha = rr.json()["id"]
    rr = client.post(f"/leagues/{league_id}/join", json={"name": "Beta", "owner": "B"})
    assert rr.status_code == 200
    t_beta = rr.json()["id"]
    rr = client.post(f"/leagues/{league_id}/join", json={"name": "Gamma", "owner": "C"})
    assert rr.status_code == 200
    t_gamma = rr.json()["id"]

    # Draft strong/medium/weak
    draft8(client, t_alpha, ["A1", "A2", "A3", "A4", "A5", "ETF1", "A6", "A7"])
    draft8(client, t_beta, ["B1", "B2", "B3", "B4", "B5", "B6", "B7", "B8"])
    draft8(client, t_gamma, ["C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8"])

    # Activate starters for scoring
    activate8(client, t_alpha)
    activate8(client, t_beta)
    activate8(client, t_gamma)

    # Single round-robin season, then score all regular weeks (projections stub)
    assert client.post(f"/schedule/season/{league_id}", params={"weeks": 0}).status_code == 200
    assert client.post(f"/standings/{league_id}/close_season").status_code == 200

    # Elo rankings
    r = client.get(f"/standings/{league_id}/elo")
    assert r.status_code == 200, r.text
    table = r.json()
    assert len(table) == 3

    names_by_order = [row["team_name"] for row in table]
    # Alpha should rank highest, Gamma lowest
    assert names_by_order[0] == "Alpha"
    assert names_by_order[-1] == "Gamma"

    # Ratings should be distinct and ordered
    elos = [row["elo"] for row in table]
    assert elos[0] > elos[1] > elos[2]
