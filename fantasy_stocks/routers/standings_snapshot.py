# fantasy_stocks/routers/standings_snapshot.py
from __future__ import annotations

from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..db import get_db
from .. import models
from .standings import _aggregate_table_rows  # reuse proven aggregation

# Distinct tag to avoid OpenAPI operation-id collisions
route = APIRouter(prefix="/standings", tags=["standings-snapshot"])

@route.get("/{league_id}/snapshot")
def standings_snapshot(league_id: int, db: Session = Depends(get_db)) -> List[dict]:
    """
    Return a PLAIN LIST of aggregate table rows (same shape as /standings/{league_id}/table).
    This matches tests that do `len(snapshot) == number_of_teams`.
    """
    league = db.get(models.League, league_id)
    if not league:
        raise HTTPException(status_code=404, detail="League not found")

    table_models = _aggregate_table_rows(db, league_id)
    return [row.model_dump() for row in table_models]
