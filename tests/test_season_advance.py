# tests/test_season_advance.py


def test_advance_scores_earliest_unscored_week(client):
    # Create league with 2 teams
    r = client.post(
        "/leagues/",
        json={
            "name": "AdvanceScore",
            "roster_slots": 14,
            "starters": 8,
            "bucket_requirements": {"X": 8},
        },
    )
    assert r.status_code == 200
    league_id = r.json()["id"]

    # Join two teams
    for nm in ["A", "B"]:
        assert (
            client.post(
                f"/leagues/{league_id}/join", json={"name": nm, "owner": nm}
            ).status_code
            == 200
        )

    # Generate one week of schedule
    assert client.post(f"/schedule/generate/{league_id}", json={}).status_code == 200

    # Before: there should be at least one unscored match
    resp = client.post(f"/season/{league_id}/advance")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["action"] == "scored_week"
    assert "week" in data and "matches_scored" in data

    # Second call should now try to generate playoffs, but 2 teams < 4 => idle/error
    # We'll just assert it doesn't crash; with 2 teams we expect an HTTP 400 if it reaches playoffs.
    # But since there can still be zero remaining matches, we call again and accept either idle or 400.
    resp2 = client.post(f"/season/{league_id}/advance")
    assert resp2.status_code in (200, 400)


def test_advance_generates_playoffs_after_season(client):
    # Seed projections (optional; scoring stub works even with zeros)
    r = client.post(
        "/players/seed",
        json=[
            {
                "symbol": "AA",
                "name": "AA",
                "is_etf": False,
                "market_cap": 2e11,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 10.0,
            },
            {
                "symbol": "BB",
                "name": "BB",
                "is_etf": False,
                "market_cap": 2e11,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 9.0,
            },
        ],
    )
    assert r.status_code == 200

    # League with 4 teams
    r = client.post(
        "/leagues/",
        json={
            "name": "AdvancePlayoffs",
            "roster_slots": 14,
            "starters": 8,
            "bucket_requirements": {"X": 8},
        },
    )
    assert r.status_code == 200
    league_id = r.json()["id"]

    for nm in ["Alphas", "Betas", "Gammas", "Deltas"]:
        assert (
            client.post(
                f"/leagues/{league_id}/join", json={"name": nm, "owner": nm[0]}
            ).status_code
            == 200
        )

    # Generate a full single round-robin season
    assert (
        client.post(f"/schedule/season/{league_id}", params={"weeks": 0}).status_code
        == 200
    )

    # Score the whole season (no unscored weeks remain)
    assert client.post(f"/standings/{league_id}/close_season").status_code == 200

    # Advance should now generate semifinals
    resp = client.post(f"/season/{league_id}/advance")
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["ok"] is True
    assert data["action"] == "generated_playoffs"
    assert "semifinals" in data and len(data["semifinals"]) == 2
