# tests/test_season_playoffs.py


def test_season_and_playoffs_flow(client):
    # 1) Create league with 4 teams
    r = client.post(
        "/leagues/",
        json={
            "name": "SeasonLeague",
            "roster_slots": 14,
            "starters": 8,
            "bucket_requirements": {
                "LARGE_CAP": 1,
                "MID_CAP": 1,
                "SMALL_CAP": 1,
                "ETF": 1,
                "DIVIDEND": 1,
                "TECH": 1,
                "INTERNATIONAL": 1,
                "WILDCARD": 1,
            },
        },
    )
    assert r.status_code == 200, r.text
    league_id = r.json()["id"]

    # 2) Join four teams
    names = [("Alphas", "A"), ("Betas", "B"), ("Gammas", "C"), ("Deltas", "D")]
    team_ids = []
    for name, owner in names:
        rr = client.post(f"/leagues/{league_id}/join", json={"name": name, "owner": owner})
        assert rr.status_code == 200, rr.text
        team_ids.append(rr.json()["id"])
    assert len(team_ids) == 4

    # 3) Generate season schedule (single round-robin => n-1 weeks for n teams)
    r = client.post(f"/schedule/season/{league_id}", params={"weeks": 0})
    assert r.status_code == 200, r.text
    season_info = r.json()
    # For 4 teams: 3 weeks, 2 matches per week
    assert season_info["weeks_created"] >= 3
    assert season_info["matches_created"] >= 6

    # 4) Weeks listing
    r = client.get(f"/schedule/{league_id}/weeks")
    assert r.status_code == 200, r.text
    weeks = r.json()
    assert isinstance(weeks, list) and len(weeks) >= 3

    # 5) Close the season (scores all weeks with projection stub)
    r = client.post(f"/standings/{league_id}/close_season")
    assert r.status_code == 200, r.text
    cs = r.json()
    assert cs["ok"] is True
    assert isinstance(cs["weeks"], list) and len(cs["weeks"]) >= 3
    assert isinstance(cs["matches_scored"], int)

    # 6) Generate playoffs (top-4 -> semifinals)
    r = client.post(f"/playoffs/generate/{league_id}")
    assert r.status_code == 200, r.text
    po = r.json()
    assert "week" in po and "semifinals" in po
    assert isinstance(po["semifinals"], list) and len(po["semifinals"]) == 2
    for m in po["semifinals"]:
        assert "home_team_id" in m and "away_team_id" in m

    # 7) Advance playoffs -> create final & third place (seed tiebreak if needed)
    r = client.post(f"/playoffs/advance/{league_id}")
    assert r.status_code == 200, r.text
    adv = r.json()
    assert "final" in adv and "third_place" in adv
    assert adv["final"] is not None
    assert adv["third_place"] is not None
    for key in ("final", "third_place"):
        assert "home_team_id" in adv[key] and "away_team_id" in adv[key]

    # 8) Inspect playoff bracket
    r = client.get(f"/playoffs/{league_id}")
    assert r.status_code == 200, r.text
    bracket = r.json()
    assert any("PO-SF" in k for k in bracket.keys())
    assert any("PO-FINAL" in k for k in bracket.keys())
    assert any("PO-THIRD" in k for k in bracket.keys())
    # Basic structure checks for each round (if present)
    for k, matches in bracket.items():
        assert isinstance(matches, list)
        for m in matches:
            assert "id" in m and "home_team_id" in m and "away_team_id" in m
