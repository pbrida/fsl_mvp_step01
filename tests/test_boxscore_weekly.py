# tests/test_boxscore_weekly.py


def test_boxscore_shows_primary_and_flex_and_totals(client):
    # Ensure a clean catalog so results are deterministic
    client.post("/players/reset")

    # Seed symbols with buckets and proj_points
    r = client.post(
        "/players/seed",
        json=[
            {
                "symbol": "LC1",
                "name": "LC1",
                "is_etf": False,
                "market_cap": 2e11,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 12.0,
            },
            {
                "symbol": "LC2",
                "name": "LC2",
                "is_etf": False,
                "market_cap": 2e11,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 11.0,
            },
            {
                "symbol": "LC3",
                "name": "LC3",
                "is_etf": False,
                "market_cap": 2e11,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 10.0,
            },
            {
                "symbol": "MC1",
                "name": "MC1",
                "is_etf": False,
                "market_cap": 5e9,
                "primary_bucket": "MID_CAP",
                "proj_points": 9.0,
            },
            {
                "symbol": "SC1",
                "name": "SC1",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 8.0,
            },
            {
                "symbol": "SC2",
                "name": "SC2",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 7.0,
            },
            {
                "symbol": "SC3",
                "name": "SC3",
                "is_etf": False,
                "market_cap": 1e9,
                "primary_bucket": "SMALL_CAP",
                "proj_points": 6.0,
            },
            {
                "symbol": "ET1",
                "name": "ET1",
                "is_etf": True,
                "market_cap": 1e11,
                "primary_bucket": "ETF",
                "proj_points": 5.0,
            },
            {
                "symbol": "X1",
                "name": "X1",
                "is_etf": False,
                "market_cap": 8e10,
                "primary_bucket": "LARGE_CAP",
                "proj_points": 4.0,
            },
        ],
    )
    assert r.status_code == 200, r.text

    # League + one team
    r = client.post(
        "/leagues/",
        json={
            "name": "Box League",
            "roster_slots": 14,
            "starters": 8,
            "bucket_requirements": {"X": 8},
        },
    )
    assert r.status_code == 200, r.text
    league_id = r.json()["id"]

    r = client.post(f"/leagues/{league_id}/join", json={"name": "Solo", "owner": "S"})
    assert r.status_code == 200, r.text
    team_id = r.json()["id"]

    # Draft >8 symbols so one is benched automatically
    picks = ["LC1", "LC2", "LC3", "MC1", "SC1", "SC2", "SC3", "ET1", "X1"]
    for sym in picks:
        rr = client.post("/draft/pick", json={"team_id": team_id, "symbol": sym})
        assert rr.status_code == 200, rr.text

    # We don't need a real scheduled week; the boxscore endpoint accepts any label.
    week_label = "2025-W01"

    # Fetch boxscore
    r = client.get(f"/boxscore/{league_id}/{week_label}/{team_id}")
    assert r.status_code == 200, r.text
    data = r.json()

    # Primary should choose top LC1 & LC2 (12+11), MC1 (9), SC1 & SC2 (8+7), ET1 (5)
    # FLEX should take next best from remaining primaries: LC3 (10) and SC3 (6)
    primary = data["primary"]
    flex = data["flex"]
    totals = data["totals"]

    # verify counts
    assert len(primary["LARGE_CAP"]) == 2
    assert len(primary["MID_CAP"]) == 1
    assert len(primary["SMALL_CAP"]) == 2
    assert len(primary["ETF"]) == 1
    assert len(flex) == 2

    # verify symbols used for flex are the best remaining
    flex_syms = {x["symbol"] for x in flex}
    assert "LC3" in flex_syms
    assert "SC3" in flex_syms

    # grand total check:
    # primary = 12+11 + 9 + (8+7) + 5 = 52
    # flex = 10 + 6 = 16
    # total = 68
    assert abs(totals["primary_points"] - 52.0) < 1e-6
    assert abs(totals["flex_points"] - 16.0) < 1e-6
    assert abs(totals["grand_total"] - 68.0) < 1e-6
