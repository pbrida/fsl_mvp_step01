def test_standings_snapshot_after_simulation(client):
    # Seed small catalog with proj_points
    r = client.post(
        "/players/seed",
        json=[
            {
                "symbol": "AA",
                "name": "AA",
                "is_etf": False,
                "market_cap": 2e11,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 12.0,
            },
            {
                "symbol": "BB",
                "name": "BB",
                "is_etf": False,
                "market_cap": 2e11,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 10.0,
            },
            {
                "symbol": "CC",
                "name": "CC",
                "is_etf": False,
                "market_cap": 5e9,
                "primary_bucket": "MID_CAP",
                "proj_points": 8.0,
            },
            {
                "symbol": "DD",
                "name": "DD",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 7.0,
            },
            {
                "symbol": "EE",
                "name": "EE",
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
                "symbol": "FX1",
                "name": "FX1",
                "is_etf": False,
                "market_cap": 2e11,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 4.0,
            },
            {
                "symbol": "FX2",
                "name": "FX2",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 3.0,
            },
        ],
    )
    assert r.status_code == 200

    # League + 2 teams
    r = client.post(
        "/leagues/",
        json={
            "name": "Snapshot League",
            "roster_slots": 14,
            "starters": 8,
            "bucket_requirements": {"X": 8},
        },
    )
    assert r.status_code == 200
    league_id = r.json()["id"]

    r = client.post(f"/leagues/{league_id}/join", json={"name": "Alpha", "owner": "A"})
    assert r.status_code == 200
    t1 = r.json()["id"]

    r = client.post(f"/leagues/{league_id}/join", json={"name": "Beta", "owner": "B"})
    assert r.status_code == 200
    t2 = r.json()["id"]

    # Give both teams 8 starters; Alpha gets higher totals
    starters_alpha = ["AA", "BB", "CC", "DD", "EE", "ETF1", "FX1", "FX2"]  # sum = 55
    starters_beta = [
        "AA",
        "BB",
        "CC",
        "DD",
        "EE",
        "ETF1",
        "FX1",
        "FX2",
    ]  # same symbols -> same 55
    # Make Beta weaker by turning two symbols to zero-projection placeholders
    r = client.post(
        "/players/seed",
        json=[
            {
                "symbol": "ZZ1",
                "name": "ZZ1",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 0.0,
            },
            {
                "symbol": "ZZ2",
                "name": "ZZ2",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 0.0,
            },
        ],
    )
    assert r.status_code == 200

    for s in starters_alpha:
        rr = client.post("/draft/pick", json={"team_id": t1, "symbol": s})
        assert rr.status_code == 200
    for s in ["AA", "BB", "CC", "DD", "EE", "ETF1", "ZZ1", "ZZ2"]:
        rr = client.post("/draft/pick", json={"team_id": t2, "symbol": s})
        assert rr.status_code == 200

    # Schedule + close week
    r = client.post(f"/schedule/generate/{league_id}", json={})
    assert r.status_code == 200
    r = client.post(f"/scoring/close_week/{league_id}")
    assert r.status_code == 200

    # Snapshot
    r = client.get(f"/standings/{league_id}/snapshot")
    assert r.status_code == 200
    table = r.json()
    assert len(table) == 2
    # Ensure fields exist
    for row in table:
        for k in [
            "team_id",
            "team_name",
            "wins",
            "losses",
            "ties",
            "games_played",
            "points_for",
            "points_against",
            "point_diff",
            "win_pct",
        ]:
            assert k in row

    # The team with more proj points that week should have more wins
    wins_by_team = {row["team_name"]: row["wins"] for row in table}
    assert wins_by_team["Alpha"] >= wins_by_team["Beta"]
