# tests/test_season_advance_progression.py


def seed_minimal_players(client):
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
                "symbol": "L1",
                "name": "L1",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 1.0,
            },
            {
                "symbol": "L2",
                "name": "L2",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 1.0,
            },
        ],
    )
    assert r.status_code == 200


def draft_full(client, team_id, syms):
    for s in syms:
        rr = client.post("/draft/pick", json={"team_id": team_id, "symbol": s})
        assert rr.status_code == 200, rr.text


def test_advance_full_playoff_progression_to_champion(client):
    seed_minimal_players(client)

    # League + 4 teams
    r = client.post(
        "/leagues/",
        json={
            "name": "Advance++",
            "roster_slots": 14,
            "starters": 8,
            "bucket_requirements": {"X": 8},
        },
    )
    assert r.status_code == 200
    league_id = r.json()["id"]

    ids = []
    for nm in ["Alpha", "Beta", "Gamma", "Delta"]:
        rr = client.post(f"/leagues/{league_id}/join", json={"name": nm, "owner": nm[0]})
        assert rr.status_code == 200
        ids.append(rr.json()["id"])
    t_alpha, t_beta, t_gamma, t_delta = ids

    # Strong to weak
    draft_full(client, t_alpha, ["A1", "A2", "A3", "A4", "A5", "ETF1", "A6", "A7"])
    draft_full(client, t_delta, ["A1", "A3", "A4", "A5", "ETF1", "A6", "A7", "L1"])
    draft_full(client, t_beta, ["A1", "A3", "A4", "A5", "ETF1", "A7", "L1", "L2"])
    draft_full(client, t_gamma, ["A3", "A4", "A5", "ETF1", "A7", "L1", "L2", "A2"])  # avoid duplicate

    # Full season, then score all regular weeks
    assert client.post(f"/schedule/season/{league_id}", params={"weeks": 0}).status_code == 200
    assert client.post(f"/standings/{league_id}/close_season").status_code == 200

    # 1) Generate semifinals
    r = client.post(f"/season/{league_id}/advance")
    assert r.status_code == 200
    data = r.json()
    assert data["action"] == "generated_playoffs"
    assert "semifinals" in data and len(data["semifinals"]) == 2

    # 2) Score semifinals
    r = client.post(f"/season/{league_id}/advance")
    assert r.status_code == 200
    data = r.json()
    assert data["action"] == "scored_week"
    assert data["week"].endswith("-PO-SF")

    # 3) Generate finals (pre-bronze or finals+bronze depending on implementation)
    r = client.post(f"/season/{league_id}/advance")
    assert r.status_code == 200
    data = r.json()
    assert data["action"] in ("generated_finals", "generated_finals_and_bronze")
    assert "final" in data

    # 4) Drive to completion, tolerant of bronze-first scoring
    # We expect ≤ 4 more steps: score bronze (optional), score finals, then season_complete.
    for _ in range(6):
        r = client.post(f"/season/{league_id}/advance")
        assert r.status_code == 200
        d = r.json()
        if d["action"] == "season_complete":
            break
        # Accept intermediary actions that occur while finishing playoffs
        assert d["action"] in ("scored_week", "idle_final_pending")
    else:
        assert False, "Did not reach season_complete in expected steps"
