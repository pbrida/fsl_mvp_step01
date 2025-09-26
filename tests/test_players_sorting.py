def test_free_agency_list_sort_by_proj_points(client):
    # Seed just the ones we care about (others may exist from prior tests)
    r = client.post("/players/seed", json=[
        {"symbol": "AAA", "name": "AAA", "is_etf": False, "market_cap": 1e10, "primary_bucket": "LARGE_CAP", "adp": 50.0, "proj_points": 80.0},
        {"symbol": "BBB", "name": "BBB", "is_etf": False, "market_cap": 5e10, "primary_bucket": "LARGE_CAP", "adp": 20.0, "proj_points": 140.0},
        {"symbol": "CCC", "name": "CCC", "is_etf": True,  "market_cap": 2e10, "primary_bucket": "ETF",       "adp": 30.0, "proj_points": 110.0},
    ])
    assert r.status_code == 200

    # League/team
    r = client.post("/leagues/", json={"name": "Sort FA", "roster_slots": 14, "starters": 8, "bucket_requirements": {"X": 8}})
    assert r.status_code == 200
    league_id = r.json()["id"]
    r = client.post(f"/leagues/{league_id}/join", json={"name": "Z", "owner": "Z"})
    assert r.status_code == 200

    # Sort by proj_points desc; other seeded symbols may exist, so check relative order
    r = client.get(f"/free-agency/{league_id}/players?sort=proj_points&order=desc")
    assert r.status_code == 200
    tickers = [x["ticker"] for x in r.json()]

    # Ensure our three are present
    for sym in ["BBB", "CCC", "AAA"]:
        assert sym in tickers

    # Assert relative ordering: BBB (140) before CCC (110) before AAA (80)
    idx = {sym: tickers.index(sym) for sym in ["BBB", "CCC", "AAA"]}
    assert idx["BBB"] < idx["CCC"] < idx["AAA"]
