# tests/test_bracket_view.py


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


def test_bracket_view_end_to_end(client):
    seed_minimal_players(client)

    # League + 4 teams
    r = client.post(
        "/leagues/",
        json={
            "name": "Bracket",
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

    # Draft (strong -> weak)
    draft_full(client, t_alpha, ["A1", "A2", "A3", "A4", "A5", "ETF1", "A6", "A7"])
    draft_full(client, t_delta, ["A1", "A3", "A4", "A5", "ETF1", "A6", "A7", "L1"])
    draft_full(client, t_beta, ["A1", "A3", "A4", "A5", "ETF1", "A7", "L1", "L2"])
    draft_full(client, t_gamma, ["A3", "A4", "A5", "ETF1", "A7", "L1", "L2", "A2"])

    # Season + score regular season
    assert client.post(f"/schedule/season/{league_id}", params={"weeks": 0}).status_code == 200
    assert client.post(f"/standings/{league_id}/close_season").status_code == 200

    # Initial bracket: regular
    r = client.get(f"/season/{league_id}/bracket")
    assert r.status_code == 200
    b = r.json()
    assert b["state"] == "regular"
    assert "seeds" in b and len(b["seeds"]) >= 4
    assert b["semifinals"] == [] and b["finals"] is None and b["bronze"] is None
    assert b["champion"] is None

    # Generate semis
    assert client.post(f"/season/{league_id}/advance").status_code == 200
    r = client.get(f"/season/{league_id}/bracket")
    b = r.json()
    assert b["state"] == "semis"
    assert isinstance(b["semifinals"], list) and len(b["semifinals"]) == 2

    # Score semis
    assert client.post(f"/season/{league_id}/advance").status_code == 200
    r = client.get(f"/season/{league_id}/bracket")
    b = r.json()
    assert b["state"] == "semis"  # finals not generated yet
    assert all(m["home_points"] is not None for m in b["semifinals"])

    # Generate finals + bronze
    assert client.post(f"/season/{league_id}/advance").status_code == 200
    r = client.get(f"/season/{league_id}/bracket")
    b = r.json()
    assert b["state"] == "finals"
    assert b["finals"] is not None and b["bronze"] is not None

    # Score bronze & finals (order independent)
    assert client.post(f"/season/{league_id}/advance").status_code == 200
    assert client.post(f"/season/{league_id}/advance").status_code == 200
    # If needed, one more call to finalize champion
    r = client.post(f"/season/{league_id}/advance")
    assert r.status_code == 200

    r = client.get(f"/season/{league_id}/bracket")
    b = r.json()
    assert b["state"] in ("finals", "complete")
    if b["state"] == "complete":
        assert b["champion"] is not None
        assert "team_id" in b["champion"] and "team_name" in b["champion"]
