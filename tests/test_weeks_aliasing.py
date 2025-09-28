# tests/test_weeks_aliasing.py

import time


def test_numeric_vs_iso_weeks_flow(client):
    # create league + two teams (unique name to avoid collisions)
    lg = client.post("/leagues/", json={"name": f"wk-alias-{time.time_ns()}"})
    assert lg.status_code in (200, 201)
    league_id = lg.json()["id"]

    a = client.post("/teams/", json={"league_id": league_id, "name": "A"})
    b = client.post("/teams/", json={"league_id": league_id, "name": "B"})
    assert a.status_code in (200, 201)
    assert b.status_code in (200, 201)
    a_id = a.json()["id"]

    # seed just enough and set simple roster
    players = [
        {"symbol": "AAPL", "name": "Apple", "is_etf": False, "bucket": "LARGE_CAP", "proj_points": 10.0},
        {"symbol": "MSFT", "name": "Microsoft", "is_etf": False, "bucket": "LARGE_CAP", "proj_points": 9.0},
        {"symbol": "IJH", "name": "Mid", "is_etf": True, "bucket": "MID_CAP", "proj_points": 8.0},
        {"symbol": "IJR", "name": "Small", "is_etf": True, "bucket": "SMALL_CAP", "proj_points": 7.0},
        {"symbol": "IWM", "name": "ETF", "is_etf": True, "bucket": "ETF", "proj_points": 6.0},
        {"symbol": "GOOGL", "name": "GOOG", "is_etf": False, "bucket": "LARGE_CAP", "proj_points": 5.0},
        {"symbol": "AMZN", "name": "AMZN", "is_etf": False, "bucket": "LARGE_CAP", "proj_points": 4.0},
        {"symbol": "VB", "name": "VB", "is_etf": True, "bucket": "SMALL_CAP", "proj_points": 3.0},
    ]
    r = client.post("/players/seed", json=players)
    assert r.status_code in (200, 201)

    for sym, bucket in [
        ("AAPL", "LARGE_CAP"),
        ("MSFT", "LARGE_CAP"),
        ("IJH", "MID_CAP"),
        ("IJR", "SMALL_CAP"),
        ("IWM", "ETF"),
        ("GOOGL", "LARGE_CAP"),
        ("AMZN", "LARGE_CAP"),
        ("VB", "SMALL_CAP"),
    ]:
        r = client.post(f"/teams/{a_id}/roster/active", json={"symbol": sym, "bucket": bucket})
        assert r.status_code in (200, 201)

    # generate schedule -> returns ISO week key
    gen = client.post(f"/schedule/generate/{league_id}", json={"weeks": 1})
    assert gen.status_code in (200, 201)
    iso_week = gen.json()["week"]
    assert isinstance(iso_week, str) and "-" in iso_week

    # numeric week must work for boxscore
    resp = client.get(f"/boxscore/{league_id}/1/{a_id}")
    assert resp.status_code == 200
    box = resp.json()

    # Accept both shapes: top-level grand_total OR totals.grand_total
    if "grand_total" in box:
        total = box["grand_total"]
    elif "totals" in box and isinstance(box["totals"], dict) and "grand_total" in box["totals"]:
        total = box["totals"]["grand_total"]
    else:
        # Fallback: derive from listed players if schema changes again
        primary_points = sum(
            p["points"]
            for group in box.get("primary", {}).values()
            for p in group
            if isinstance(p, dict) and "points" in p
        )
        flex_points = sum(p["points"] for p in box.get("flex", []) if isinstance(p, dict) and "points" in p)
        total = primary_points + flex_points

    assert total > 0
