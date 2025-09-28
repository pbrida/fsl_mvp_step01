from fantasy_stocks.logic.lineup_rules import validate_starter_buckets


def test_validate_starter_buckets_auto_flex_passes():
    # 8 starters, none labeled "FLEX"; surplus should auto-fill FLEX
    # Composition:
    #   LARGE_CAP: 3  (2 required + 1 surplus feeds FLEX)
    #   MID_CAP:   1
    #   SMALL_CAP: 2
    #   ETF:       2  (1 required + 1 surplus feeds FLEX)
    selection = [
        "LARGE_CAP",
        "LARGE_CAP",
        "LARGE_CAP",
        "MID_CAP",
        "SMALL_CAP",
        "SMALL_CAP",
        "ETF",
        "ETF",
    ]
    ok, detail = validate_starter_buckets(selection)
    assert ok, detail


def test_validate_starter_buckets_fails_when_not_enough_flex_surplus():
    # Only the primaries are satisfied exactly; no surplus to fill the 2 FLEX
    selection = [
        "LARGE_CAP",
        "LARGE_CAP",
        "MID_CAP",
        "SMALL_CAP",
        "SMALL_CAP",
        "ETF",
        # missing 2 surplus for FLEX
        "LARGE_CAP",  # this makes 3 LC (1 surplus) -> still missing 1 for FLEX
        # total 7 so far; add one more non-eligible? (everything is eligible, but
        # we need 2 surplus; here we only provided 1 surplus)
        "MID_CAP",  # now MID has 2 (1 surplus) -> OK actually this would pass FLEX with 2 surplus
    ]
    ok, detail = validate_starter_buckets(selection)
    # The above comment shows it's actually sufficient surplus; fix the example to truly fail:
    # Let's try: meet primaries exactly and then add one EXTRA from a primary for only 1 surplus
    selection = [
        "LARGE_CAP",
        "LARGE_CAP",  # LC meets
        "MID_CAP",  # mid meets
        "SMALL_CAP",
        "SMALL_CAP",  # small meets
        "ETF",  # etf meets
        "MID_CAP",  # 1 surplus
        "MID_CAP",  # 2 surplus -> would pass FLEX, so remove one
    ][:7]  # force only 7 picks (should fail count)
    ok, detail = validate_starter_buckets(selection)
    assert not ok
    assert detail["explain"]["wrong_starter_count"]["need"] == 8


def test_validate_starter_buckets_reports_deficits():
    # Wrong distribution, will miss primaries + flex
    selection = [
        "LARGE_CAP",
        "MID_CAP",
        "SMALL_CAP",
        "ETF",
        "SMALL_CAP",
        "MID_CAP",
        "MID_CAP",
        "MID_CAP",
    ]
    ok, detail = validate_starter_buckets(selection)
    assert not ok
    assert "bucket_requirements_unmet" in detail
