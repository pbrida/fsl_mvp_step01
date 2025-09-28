# tests/test_free_agency_registry.py


def test_fa_claim_with_ticker_resolves_bucket_and_auto_places(client):
    r = client.post(
        "/leagues/",
        json={
            "name": "FA Registry",
            "roster_slots": 14,
            "starters": 8,
            "bucket_requirements": {"Z": 8},
        },
    )
    assert r.status_code == 200
    league_id = r.json()["id"]

    r = client.post(f"/leagues/{league_id}/join", json={"name": "Owls", "owner": "O"})
    assert r.status_code == 200
    team_id = r.json()["id"]

    # Claim SHOP (mapped to SMALL_CAP)
    r = client.post(
        f"/free-agency/{league_id}/claim",
        json={
            "league_id": league_id,
            "team_id": team_id,
            "player_id": 123,  # not used when ticker is provided
            "ticker": "SHOP",
        },
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["bucket_resolved"] is True
    assert data["placement"] is not None

    roster = client.get(f"/draft/roster/{team_id}").json()
    assert len(roster) == 1
    assert roster[0]["symbol"] == "SHOP"
    assert roster[0]["bucket"] == "SMALL_CAP"
    assert roster[0]["is_active"] is True  # fills SMALL_CAP primary if open
