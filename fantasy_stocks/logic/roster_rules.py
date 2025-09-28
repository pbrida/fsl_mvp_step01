from pydantic import BaseModel, Field

# ---- Buckets (primary positions) ----
BUCKET_LARGE_CAP = "LARGE_CAP"
BUCKET_MID_CAP = "MID_CAP"
BUCKET_SMALL_CAP = "SMALL_CAP"
BUCKET_ETF = "ETF"

PRIMARY_BUCKETS: list[str] = [
    BUCKET_LARGE_CAP,
    BUCKET_MID_CAP,
    BUCKET_SMALL_CAP,
    BUCKET_ETF,
]

# FLEX can accept any primary bucket
FLEX_ELIGIBILITY: list[str] = PRIMARY_BUCKETS.copy()

# ---- Fixed starter slots (exactly 8 total) ----
FIXED_STARTER_SLOTS: dict[str, int] = {
    BUCKET_LARGE_CAP: 2,
    BUCKET_MID_CAP: 1,
    BUCKET_SMALL_CAP: 2,
    BUCKET_ETF: 1,
    "FLEX": 2,
}


class RosterRules(BaseModel):
    starters: dict[str, int] = Field(..., description="Exact starter slot counts by bucket (includes FLEX).")
    roster_size: int = Field(14, description="Total roster size (starters + bench).")
    starters_total: int = Field(8, description="Total number of starters.")
    bench_size: int = Field(6, description="Total bench slots.")
    flex_eligibility: list[str] = Field(..., description="Which primary buckets can fill FLEX.")

    @classmethod
    def fixed(cls) -> "RosterRules":
        return cls(
            starters=FIXED_STARTER_SLOTS.copy(),
            roster_size=14,
            starters_total=8,
            bench_size=14 - 8,
            flex_eligibility=FLEX_ELIGIBILITY.copy(),
        )


def get_fixed_rules() -> RosterRules:
    """Public accessor for the project-wide fixed roster rules."""
    return RosterRules.fixed()
