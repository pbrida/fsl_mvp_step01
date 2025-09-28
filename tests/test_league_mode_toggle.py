def test_league_mode_toggle_roundtrip(client):
    # Create a league (defaults to PROJECTIONS in current router)
    r = client.post("/leagues/", json={"name": "Toggle League"})
    assert r.status_code == 200
    league_id = r.json()["id"]

    # Verify default
    r_get = client.get(f"/leagues/{league_id}")
    assert r_get.status_code == 200
    assert r_get.json()["scoring_mode"] == "PROJECTIONS"

    # Toggle to LIVE
    r_patch = client.patch(f"/leagues/{league_id}/mode", json={"scoring_mode": "LIVE"})
    assert r_patch.status_code == 200
    assert r_patch.json()["scoring_mode"] == "LIVE"

    # Toggle back to PROJECTIONS (idempotent ok)
    r_patch2 = client.patch(f"/leagues/{league_id}/mode", json={"scoring_mode": "PROJECTIONS"})
    assert r_patch2.status_code == 200
    assert r_patch2.json()["scoring_mode"] == "PROJECTIONS"
