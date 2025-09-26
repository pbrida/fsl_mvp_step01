def test_players_search_and_available_in_league(client):
    # Reset catalog to avoid cross-test pollution
    client.post("/players/reset")

    # Seed some securities
    seed = [
        {"symbol": "AAPL", "name": "Apple", "is_etf": False, "market_cap": 2_500_000_000_000, "primary_bucket": "LARGE_CAP"},
        {"symbol": "VTI",  "name": "Vanguard Total Market", "is_etf": True, "market_cap": 300_000_000_000, "primary_bucket": "ETF"},
        {"symbol": "SHOP", "name": "Shopify", "is_etf": False, "market_cap": 80_000_000_000, "primary_bucket": "SMALL_CAP"},
    ]
    r = client.post("/players/seed", json=seed)
    assert r.status_code == 200, r.text

    # Create league + two teams
    r = client.post("/leagues/", json={"name": "Search League", "roster_slots": 14, "starters": 8, "bucket_requirements": {"X": 8}})
    assert r.status_code == 200
    league_id = r.json()["id"]

    r = client.post(f"/leagues/{league_id}/join", json={"name": "One", "owner": "O"})
    assert r.status_code == 200
    team1 = r.json()["id"]

    r = client.post(f"/leagues/{league_id}/join", json={"name": "Two", "owner": "T"})
    assert r.status_code == 200
    team2 = r.json()["id"]

    # Draft AAPL to team1 so it's no longer available
    r = client.post("/draft/pick", json={"team_id": team1, "symbol": "AAPL"})
    assert r.status_code == 200

    # Search all players available in this league -> should exclude AAPL
    r = client.get(f"/players/search?available_in_league={league_id}")
    assert r.status_code == 200
    lst = r.json()
    syms = {x["symbol"] for x in lst}
    assert "AAPL" not in syms
    assert "VTI" in syms
    assert "SHOP" in syms

    # Filter by bucket = ETF -> should return only VTI
    r = client.get(f"/players/search?available_in_league={league_id}&bucket=ETF")
    assert r.status_code == 200
    lst = r.json()
    assert [x["symbol"] for x in lst] == ["VTI"]

    # Text search by name/symbol
    r = client.get(f"/players/search?available_in_league={league_id}&q=shop")
    assert r.status_code == 200
    lst = r.json()
    assert [x["symbol"] for x in lst] == ["SHOP"]
