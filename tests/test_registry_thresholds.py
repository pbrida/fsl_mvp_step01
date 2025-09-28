def test_db_derivation_via_market_cap_thresholds(client):
    # Create league + team
    r = client.post(
        "/leagues/",
        json={
            "name": "Thresh",
            "roster_slots": 14,
            "starters": 8,
            "bucket_requirements": {"X": 8},
        },
    )
    assert r.status_code == 200
    league_id = r.json()["id"]

    r = client.post(f"/leagues/{league_id}/join", json={"name": "Caps", "owner": "C"})
    assert r.status_code == 200
    team_id = r.json()["id"]

    # Seed NEWCO with no primary_bucket but with market_cap that implies SMALL_CAP
    r = client.post(
        "/players/seed",
        json=[
            {
                "symbol": "NEWCO",
                "name": "New Company",
                "is_etf": False,
                "market_cap": 500_000_000,  # < $2B => SMALL_CAP
                "primary_bucket": None,
            }
        ],
    )
    assert r.status_code == 200

    r = client.post("/draft/pick", json={"team_id": team_id, "symbol": "NEWCO"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["bucket_resolved"] is True
    assert data["slot"]["bucket"] == "SMALL_CAP"
    # Should auto-activate toward SMALL_CAP primary
    roster = client.get(f"/draft/roster/{team_id}").json()
    assert roster[0]["is_active"] is True
