def test_read_roster_rules(client):
    r = client.get("/leagues/roster-rules")
    assert r.status_code == 200
    data = r.json()
    assert data["starters"]["LARGE_CAP"] == 2
    assert data["starters"]["MID_CAP"] == 1
    assert data["starters"]["SMALL_CAP"] == 2
    assert data["starters"]["ETF"] == 1
    assert data["starters"]["FLEX"] == 2
    assert data["starters_total"] == 8
    assert data["roster_size"] == 14
    assert data["bench_size"] == 6
    # FLEX accepts all primary buckets
    for b in ["LARGE_CAP", "MID_CAP", "SMALL_CAP", "ETF"]:
        assert b in data["flex_eligibility"]
