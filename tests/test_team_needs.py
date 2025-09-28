# tests/test_team_needs.py


def test_team_needs_primary_then_flex(client):
    # Seed a few symbols with known buckets
    r = client.post(
        "/players/seed",
        json=[
            {
                "symbol": "AAPL",
                "name": "Apple",
                "is_etf": False,
                "market_cap": 2.5e12,
                "primary_bucket": "LARGE_CAP",
            },
            {
                "symbol": "GOOGL",
                "name": "Alphabet",
                "is_etf": False,
                "market_cap": 1.8e12,
                "primary_bucket": "LARGE_CAP",
            },
            {
                "symbol": "VTI",
                "name": "Vanguard Total",
                "is_etf": True,
                "market_cap": 3e11,
                "primary_bucket": "ETF",
            },
            {
                "symbol": "SHOP",
                "name": "Shopify",
                "is_etf": False,
                "market_cap": 8e10,
                "primary_bucket": "SMALL_CAP",
            },
            {
                "symbol": "NEWM",
                "name": "New Mid",
                "is_etf": False,
                "market_cap": 5e9,
                "primary_bucket": "MID_CAP",
            },
        ],
    )
    assert r.status_code == 200

    # League + team
    r = client.post(
        "/leagues/",
        json={
            "name": "Needs League",
            "roster_slots": 14,
            "starters": 8,
            "bucket_requirements": {"X": 8},
        },
    )
    assert r.status_code == 200
    league_id = r.json()["id"]

    r = client.post(f"/leagues/{league_id}/join", json={"name": "Hawks", "owner": "H"})
    assert r.status_code == 200
    team_id = r.json()["id"]

    # Draft: fill 2x LARGE, 1x ETF, 1x SMALL, 1x MID  => 5 active starters, no surplus -> FLEX 0 yet
    for sym in ["AAPL", "GOOGL", "VTI", "SHOP", "NEWM"]:
        rr = client.post("/draft/pick", json={"team_id": team_id, "symbol": sym})
        assert rr.status_code == 200, rr.text

    # Check needs
    r = client.get(f"/teams/{team_id}/needs")
    assert r.status_code == 200, r.text
    data = r.json()

    req = data["requirements"]
    # Primary buckets:
    assert req["LARGE_CAP"]["need"] == 2 and req["LARGE_CAP"]["got"] == 2
    assert req["MID_CAP"]["need"] == 1 and req["MID_CAP"]["got"] == 1
    assert req["SMALL_CAP"]["need"] == 2 and req["SMALL_CAP"]["got"] == 1  # still need 1 small
    assert req["ETF"]["need"] == 1 and req["ETF"]["got"] == 1
    # FLEX not filled yet (no surplus primaries)
    assert req["FLEX"]["need"] == 2 and req["FLEX"]["got"] == 0

    # Summary:
    assert data["summary"]["starters_required"] == 8
    assert data["summary"]["starters_got"] == (2 + 1 + 1 + 1 + 0)  # primary_got sum + flex_got = 5
    assert data["summary"]["starters_remaining"] == 3
