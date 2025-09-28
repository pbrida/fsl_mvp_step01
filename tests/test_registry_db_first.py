def test_db_resolution_overrides_dict(client):
    # Create league + team
    r = client.post(
        "/leagues/",
        json={
            "name": "DB First",
            "roster_slots": 14,
            "starters": 8,
            "bucket_requirements": {"X": 8},
        },
    )
    assert r.status_code == 200
    league_id = r.json()["id"]

    r = client.post(f"/leagues/{league_id}/join", json={"name": "DBTeam", "owner": "D"})
    assert r.status_code == 200
    team_id = r.json()["id"]

    # Seed MSFT as MID_CAP in DB (dict says LARGE_CAP, DB should win)
    r = client.post(
        "/players/seed",
        json=[
            {
                "symbol": "MSFT",
                "name": "Microsoft",
                "is_etf": False,
                "market_cap": 5_000_000_000,  # mid band by our thresholds
                "primary_bucket": "MID_CAP",  # cache it explicitly
            }
        ],
    )
    assert r.status_code == 200, r.text

    # Draft MSFT
    r = client.post("/draft/pick", json={"team_id": team_id, "symbol": "MSFT"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["bucket_resolved"] is True
    assert data["slot"]["bucket"] == "MID_CAP"  # DB mapping wins

    # Should be active toward MID_CAP primary
    roster = client.get(f"/draft/roster/{team_id}").json()
    assert roster[0]["is_active"] is True
