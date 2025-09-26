# tests/test_free_agency_autoplace.py

def test_free_agency_auto_placement_primary_then_flex_then_bench(client):
    # Create a league (server enforces fixed roster rules)
    r = client.post("/leagues/", json={
        "name": "FA Test League",
        "roster_slots": 14,
        "starters": 8,
        "bucket_requirements": {"LARGE_CAP": 8}  # ignored by server, fixed rules apply
    })
    assert r.status_code == 200, r.text
    league_id = r.json()["id"]

    # Join a team
    r = client.post(f"/leagues/{league_id}/join", json={"name": "Sharks", "owner": "Sam"})
    assert r.status_code == 200, r.text
    team_id = r.json()["id"]

    # Helper to claim a "player" into team with a chosen primary bucket
    def claim(pid: int, bucket: str = "LARGE_CAP"):
        return client.post(
            f"/free-agency/{league_id}/claim",
            json={
                "league_id": league_id,
                "team_id": team_id,
                "player_id": pid,
                "primary_bucket": bucket
            }
        )

    # Make 5 LARGE_CAP claims in a row
    # Expect: first 2 fill LC primaries, next 2 fill FLEX (surplus), last one benched
    for pid in [9001, 9002, 9003, 9004, 9005]:
        r = claim(pid, "LARGE_CAP")
        assert r.status_code == 200, r.text
        resp = r.json()
        assert resp["ok"] is True

    # Fetch roster and check active counts
    roster = client.get(f"/draft/roster/{team_id}").json()
    assert len(roster) == 5  # 5 claims -> 5 roster slots

    active = [s for s in roster if s["is_active"]]
    bench  = [s for s in roster if not s["is_active"]]

    # With fixed rules, after 4 active LC starters (2 primary + 2 FLEX), the 5th must be bench
    assert len(active) == 4
    assert len(bench) == 1

    # All should be tagged LC bucket (we default to storing the given primary)
    assert all(s["bucket"] == "LARGE_CAP" for s in roster)
