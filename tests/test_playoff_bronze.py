# tests/test_playoff_bronze.py


def test_bronze_match_generation_and_scoring(client):
    # Minimal seeding (projections)
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

    # League + 4 teams
    r = client.post(
        "/leagues/",
        json={
            "name": "Bronze League",
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

    # Draft (A strongest → ... → weakest)
    for s in ["A1", "A2", "A3", "A4", "A5", "ETF1", "A6", "A7"]:
        assert client.post("/draft/pick", json={"team_id": t_alpha, "symbol": s}).status_code == 200
    for s in ["A1", "A3", "A4", "A5", "ETF1", "A6", "A7", "L1"]:
        assert client.post("/draft/pick", json={"team_id": t_delta, "symbol": s}).status_code == 200
    for s in ["A1", "A3", "A4", "A5", "ETF1", "A7", "L1", "L2"]:
        assert client.post("/draft/pick", json={"team_id": t_beta, "symbol": s}).status_code == 200
    for s in ["A3", "A4", "A5", "ETF1", "A7", "L1", "L2", "A2"]:
        assert client.post("/draft/pick", json={"team_id": t_gamma, "symbol": s}).status_code == 200

    # Create a season and score all regular-season weeks
    assert client.post(f"/schedule/season/{league_id}", params={"weeks": 0}).status_code == 200
    assert client.post(f"/standings/{league_id}/close_season").status_code == 200

    # Generate semis
    r = client.post(f"/season/{league_id}/advance")
    assert r.status_code == 200
    assert r.json()["action"] == "generated_playoffs"

    # Score semis
    r = client.post(f"/season/{league_id}/advance")
    assert r.status_code == 200
    assert r.json()["action"] == "scored_week"
    assert r.json()["week"].endswith("-PO-SF")

    # Generate finals + bronze
    r = client.post(f"/season/{league_id}/advance")
    assert r.status_code == 200
    data = r.json()
    assert data["action"] == "generated_finals_and_bronze"
    assert "final" in data and "bronze" in data

    # Score bronze first (lexicographically earlier week '-PO-3P')
    r = client.post(f"/season/{league_id}/advance")
    assert r.status_code == 200
    data = r.json()
    assert data["action"] == "scored_week"
    assert data["week"].endswith("-PO-3P")

    # Score finals
    r = client.post(f"/season/{league_id}/advance")
    assert r.status_code == 200
    data = r.json()
    # Either finals just scored or already completed
    assert data["action"] in ("scored_week", "season_complete")

    # Final call should yield season_complete + champion
    if data["action"] != "season_complete":
        r = client.post(f"/season/{league_id}/advance")
        assert r.status_code == 200
        data = r.json()
    assert data["action"] == "season_complete"
    assert "champion_team_id" in data and "champion_team_name" in data
