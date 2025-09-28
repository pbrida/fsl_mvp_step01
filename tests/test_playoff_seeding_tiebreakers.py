# tests/test_playoff_seeding_tiebreakers.py


def test_playoff_seeding_follows_tiebreakers(client):
    # Seed projections
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
            # Additional low scorers to create separation
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
    assert r.status_code == 200, r.text

    # League + 4 teams
    r = client.post(
        "/leagues/",
        json={
            "name": "SeedTB League",
            "roster_slots": 14,
            "starters": 8,
            "bucket_requirements": {"X": 8},
        },
    )
    assert r.status_code == 200
    league_id = r.json()["id"]

    # Join four teams
    ids = []
    for nm in ["Alpha", "Beta", "Gamma", "Delta"]:
        rr = client.post(
            f"/leagues/{league_id}/join", json={"name": nm, "owner": nm[0]}
        )
        assert rr.status_code == 200, rr.text
        ids.append(rr.json()["id"])
    t_alpha, t_beta, t_gamma, t_delta = ids

    # Draft: Alpha strongest, Beta medium, Gamma weakest, Delta medium-strong
    for s in ["A1", "A2", "A3", "A4", "A5", "ETF1", "A6", "A7"]:
        assert (
            client.post(
                "/draft/pick", json={"team_id": t_alpha, "symbol": s}
            ).status_code
            == 200
        )
    for s in ["A1", "A3", "A4", "A5", "ETF1", "A6", "A7", "L1"]:
        assert (
            client.post(
                "/draft/pick", json={"team_id": t_delta, "symbol": s}
            ).status_code
            == 200
        )
    for s in ["A1", "A3", "A4", "A5", "ETF1", "A7", "L1", "L2"]:
        assert (
            client.post(
                "/draft/pick", json={"team_id": t_beta, "symbol": s}
            ).status_code
            == 200
        )
    # FIX: avoid duplicate "L1" — use "A2" for the last pick
    for s in ["A3", "A4", "A5", "ETF1", "A7", "L1", "L2", "A2"]:
        assert (
            client.post(
                "/draft/pick", json={"team_id": t_gamma, "symbol": s}
            ).status_code
            == 200
        )

    # One week schedule + score
    assert client.post(f"/schedule/generate/{league_id}", json={}).status_code == 200
    assert client.post(f"/scoring/close_week/{league_id}").status_code == 200

    # Tiebreaker order
    tr = client.get(f"/standings/{league_id}/tiebreakers")
    assert tr.status_code == 200, tr.text
    tb_rows = tr.json()
    tb_ids_in_order = [r["team_id"] for r in tb_rows[:4]]

    # Generate playoffs and infer seed order from bracket (1v4, 2v3)
    pr = client.post(f"/playoffs/generate/{league_id}")
    assert pr.status_code == 200, pr.text
    semis = pr.json()["semifinals"]
    # bracket order: [s1, s2, s3, s4] as [m1.home, m2.home, m2.away, m1.away]
    bracket_order = [
        semis[0]["home_team_id"],
        semis[1]["home_team_id"],
        semis[1]["away_team_id"],
        semis[0]["away_team_id"],
    ]

    assert tb_ids_in_order == bracket_order
