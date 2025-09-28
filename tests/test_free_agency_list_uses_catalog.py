def test_free_agency_list_uses_catalog_and_excludes_rostered(client):
    # Reset catalog to avoid cross-test pollution
    client.post("/players/reset")

    # Seed
    seed = [
        {
            "symbol": "AAPL",
            "name": "Apple",
            "is_etf": False,
            "market_cap": 2_500_000_000_000,
            "primary_bucket": "LARGE_CAP",
        },
        {
            "symbol": "VTI",
            "name": "Vanguard Total Market",
            "is_etf": True,
            "market_cap": 300_000_000_000,
            "primary_bucket": "ETF",
        },
        {
            "symbol": "SHOP",
            "name": "Shopify",
            "is_etf": False,
            "market_cap": 80_000_000_000,
            "primary_bucket": "SMALL_CAP",
        },
    ]
    r = client.post("/players/seed", json=seed)
    assert r.status_code == 200

    # League + team
    r = client.post(
        "/leagues/",
        json={
            "name": "FA Catalog League",
            "roster_slots": 14,
            "starters": 8,
            "bucket_requirements": {"X": 8},
        },
    )
    assert r.status_code == 200
    league_id = r.json()["id"]

    r = client.post(f"/leagues/{league_id}/join", json={"name": "Cats", "owner": "C"})
    assert r.status_code == 200
    team_id = r.json()["id"]

    # Draft AAPL to remove it from FA pool
    r = client.post("/draft/pick", json={"team_id": team_id, "symbol": "AAPL"})
    assert r.status_code == 200

    # Free agency list should exclude AAPL, include VTI/SHOP
    r = client.get(f"/free-agency/{league_id}/players")
    assert r.status_code == 200
    fa = r.json()
    tickers = {x["ticker"] for x in fa}
    assert "AAPL" not in tickers
    assert "VTI" in tickers
    assert "SHOP" in tickers

    # Filtering by bucket ETF -> only VTI
    r = client.get(f"/free-agency/{league_id}/players?bucket=ETF")
    assert r.status_code == 200
    fa = r.json()
    assert [x["ticker"] for x in fa] == ["VTI"]
