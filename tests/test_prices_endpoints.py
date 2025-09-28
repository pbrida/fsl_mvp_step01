import json
from io import BytesIO

import pytest


def test_openapi_exposes_prices_paths(client):
    r = client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    paths = spec.get("paths", {})
    assert "/prices/bulk" in paths
    assert "/prices/csv" in paths


def test_prices_bulk_upsert_is_idempotent(client):
    rows = [
        {"symbol": "LC1", "date": "2025-09-15", "open": 100.0, "close": 110.0},
        {"symbol": "SM1", "date": "2025-09-16", "open": 50.0, "close": 45.0},
    ]
    r1 = client.post("/prices/bulk", json=rows)
    assert r1.status_code == 200
    j1 = r1.json()
    assert j1 == {"inserted": 2, "updated": 0}

    # same payload → no changes
    r2 = client.post("/prices/bulk", json=rows)
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2 == {"inserted": 0, "updated": 0}

    # modify one value → 1 updated
    rows_update = [
        {"symbol": "LC1", "date": "2025-09-15", "open": 100.0, "close": 111.0},
    ]
    r3 = client.post("/prices/bulk", json=rows_update)
    assert r3.status_code == 200
    j3 = r3.json()
    assert j3["inserted"] == 0
    assert j3["updated"] == 1


def test_prices_csv_upload_with_good_data(client):
    csv_content = ("symbol,date,open,close\nAAPL,2025-09-15,226.12,228.43\nSPY,2025-09-15,555.10,557.20\n").encode(
        "utf-8"
    )

    files = {"file": ("prices.csv", BytesIO(csv_content), "text/csv")}
    r = client.post("/prices/csv", files=files)
    assert r.status_code == 200
    j = r.json()
    assert j["inserted"] == 2
    assert j["updated"] == 0

    # re-upload → no-op
    r2 = client.post("/prices/csv", files=files)
    assert r2.status_code == 200
    j2 = r2.json()
    assert j2["inserted"] == 0
    assert j2["updated"] == 0


@pytest.mark.parametrize(
    "csv_text, expected_status, expected_msg_frag",
    [
        ("sym,date,open,close\nAAPL,2025-09-15,1,2\n", 400, "headers"),
        ("symbol,date,open,close\nAAPL,15-09-2025,1,2\n", 400, "invalid date"),
        ("symbol,date,open,close\nAAPL,2025-09-15,one,2\n", 400, "invalid number"),
    ],
)
def test_prices_csv_validation_errors(client, csv_text, expected_status, expected_msg_frag):
    files = {"file": ("prices.csv", BytesIO(csv_text.encode("utf-8")), "text/csv")}
    r = client.post("/prices/csv", files=files)
    assert r.status_code == expected_status
    assert expected_msg_frag in json.dumps(r.json()).lower()
