# tests/test_players_csv_ingest.py

def test_players_csv_ingest_and_search(client):
    # Reset catalog to avoid cross-test pollution
    client.post("/players/reset")

    csv_text = """symbol,name,is_etf,market_cap,sector,primary_bucket
AAPL,Apple,false,2500000000000,Technology,LARGE_CAP
VTI,Vanguard Total Market,true,300000000000,ETF,ETF
SHOP,Shopify,false,80000000000,Technology,SMALL_CAP
"""
    # ... rest unchanged ...


    # Ingest
    r = client.post("/players/ingest_csv", json={"csv": csv_text, "upsert": True})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["ok"] is True
    assert set(data["upserted"]) == {"AAPL", "VTI", "SHOP"}

    # Search all
    r = client.get("/players/search")
    assert r.status_code == 200
    symbols = sorted([x["symbol"] for x in r.json()])
    assert symbols == ["AAPL", "SHOP", "VTI"]

    # Filter by bucket
    r = client.get("/players/search?bucket=ETF")
    assert r.status_code == 200
    etfs = [x["symbol"] for x in r.json()]
    assert etfs == ["VTI"]

    # Text search
    r = client.get("/players/search?q=shop")
    assert r.status_code == 200
    res = [x["symbol"] for x in r.json()]
    assert res == ["SHOP"]
