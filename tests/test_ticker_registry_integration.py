# tests/test_ticker_registry_integration.py


def test_draft_uses_registry_for_known_ticker(client):
    # Create league + team
    r = client.post(
        "/leagues/",
        json={
            "name": "Registry League",
            "roster_slots": 14,
            "starters": 8,
            "bucket_requirements": {"X": 8},
        },
    )
    assert r.status_code == 200
    league_id = r.json()["id"]

    r = client.post(f"/leagues/{league_id}/join", json={"name": "Jets", "owner": "J"})
    assert r.status_code == 200
    team_id = r.json()["id"]

    # Pick VTI (mapped to ETF)
    r = client.post("/draft/pick", json={"team_id": team_id, "symbol": "VTI"})
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["bucket_resolved"] is True
    slot = payload["slot"]
    assert slot["bucket"] == "ETF"

    # It should auto-activate, contributing to ETF primary
    roster = client.get(f"/draft/roster/{team_id}").json()
    assert len(roster) == 1
    assert roster[0]["symbol"] == "VTI"
    assert roster[0]["bucket"] == "ETF"
    assert roster[0]["is_active"] is True


def test_draft_unknown_ticker_stays_inactive(client):
    r = client.post(
        "/leagues/",
        json={
            "name": "Unknown League",
            "roster_slots": 14,
            "starters": 8,
            "bucket_requirements": {"Y": 8},
        },
    )
    assert r.status_code == 200
    league_id = r.json()["id"]

    r = client.post(f"/leagues/{league_id}/join", json={"name": "Crows", "owner": "C"})
    assert r.status_code == 200
    team_id = r.json()["id"]

    # Unknown ticker 'XYZ' => no registry mapping
    r = client.post("/draft/pick", json={"team_id": team_id, "symbol": "XYZ"})
    assert r.status_code == 200, r.text
    payload = r.json()
    assert payload["bucket_resolved"] is False
    assert payload["hint"] is not None

    roster = client.get(f"/draft/roster/{team_id}").json()
    assert len(roster) == 1
    assert roster[0]["symbol"] == "XYZ"
    assert roster[0]["bucket"] is None
    assert roster[0]["is_active"] is False
