# fantasy_stocks/logic/lineup_rules.py
from __future__ import annotations
from typing import Dict, List, Tuple

BUCKET_LARGE_CAP = "LARGE_CAP"
BUCKET_MID_CAP = "MID_CAP"
BUCKET_SMALL_CAP = "SMALL_CAP"
BUCKET_ETF = "ETF"
FLEX = "FLEX"

PRIMARY = [BUCKET_LARGE_CAP, BUCKET_MID_CAP, BUCKET_SMALL_CAP, BUCKET_ETF]
FLEX_ELIGIBLE = set(PRIMARY)

REQUIRED: Dict[str, int] = {
    BUCKET_LARGE_CAP: 2,
    BUCKET_MID_CAP: 1,
    BUCKET_SMALL_CAP: 2,
    BUCKET_ETF: 1,
    FLEX: 2,
}

STARTERS_TOTAL = sum(v for k, v in REQUIRED.items() if k != FLEX) + REQUIRED[FLEX]


def _count(buckets: List[str]) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for b in buckets:
        out[b] = out.get(b, 0) + 1
    return out


def validate_starter_buckets(selected_buckets: List[str]) -> Tuple[bool, Dict]:
    """
    Validates an 8-slot starter set against fixed rules, treating FLEX as a wildcard.
    - selected_buckets: list of primary bucket labels for the 8 starters.
      You do NOT need to include 'FLEX' in this list; FLEX is derived from surplus.
    Returns: (ok, detail)
    """
    detail: Dict = {"required": REQUIRED.copy(), "counts": {}, "explain": {}}

    if len(selected_buckets) != STARTERS_TOTAL:
        detail["explain"]["wrong_starter_count"] = {
            "need": STARTERS_TOTAL, "got": len(selected_buckets)
        }
        return False, detail

    counts = _count(selected_buckets)
    detail["counts"] = counts

    # 1) Satisfy primaries
    deficits: Dict[str, Dict[str, int]] = {}
    surplus_pool = 0
    for k in PRIMARY:
        need = REQUIRED[k]
        got = counts.get(k, 0)
        if got < need:
            deficits[k] = {"need": need, "got": got, "missing": need - got}
        else:
            surplus_pool += (got - need)

    # 2) Use surplus to fill FLEX
    flex_needed = REQUIRED[FLEX]
    if flex_needed > 0:
        # Only buckets in FLEX_ELIGIBLE can feed FLEX; everything in PRIMARY is eligible.
        eligible_surplus = 0
        for k in PRIMARY:
            got = counts.get(k, 0)
            need = REQUIRED[k]
            if got > need and k in FLEX_ELIGIBLE:
                eligible_surplus += (got - need)

        # Also, if we didn't meet some primaries, try to borrow from OTHER primaries for FLEX? No.
        # FLEX must be filled AFTER primaries are satisfied; so only true surplus counts.
        if eligible_surplus < flex_needed:
            deficits[FLEX] = {"need": flex_needed, "got": eligible_surplus}

    if deficits:
        detail["bucket_requirements_unmet"] = deficits
        return False, detail

    return True, detail
