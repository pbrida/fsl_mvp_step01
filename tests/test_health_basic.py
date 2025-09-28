def test_health_ping(client):
    r = client.get("/health/ping")
    assert r.status_code == 200
    js = r.json()
    assert js["ok"] is True
    assert js["ping"] == "pong"
