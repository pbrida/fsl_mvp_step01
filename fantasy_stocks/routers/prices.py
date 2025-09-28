# fantasy_stocks/routers/prices.py
import csv
import io
from datetime import date

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Price
from ..schemas import PriceIn, PriceUpsertResult

router = APIRouter(prefix="/prices", tags=["prices"])


def _upsert_prices(db: Session, rows: list[PriceIn]) -> tuple[int, int]:
    inserted, updated = 0, 0
    for r in rows:
        symbol = r.symbol.upper()
        d: date = r.date
        open_ = r.open
        close_ = r.close

        existing = db.query(Price).filter(Price.symbol == symbol, Price.date == d).one_or_none()
        if existing:
            changed = False
            if open_ is not None and existing.open != open_:
                existing.open = open_
                changed = True
            if close_ is not None and existing.close != close_:
                existing.close = close_
                changed = True
            if changed:
                updated += 1
        else:
            db.add(Price(symbol=symbol, date=d, open=open_, close=close_))
            inserted += 1
    db.commit()
    return inserted, updated


@router.post("/bulk", response_model=PriceUpsertResult)
def bulk_prices(rows: list[PriceIn], db: Session = Depends(get_db)):
    # FastAPI/Pydantic will already have validated each item as PriceIn (date is a real date)
    ins, upd = _upsert_prices(db, rows)
    return {"inserted": ins, "updated": upd}


@router.post("/csv", response_model=PriceUpsertResult)
async def upload_prices_csv(file: UploadFile = File(...), db: Session = Depends(get_db)):
    filename: str | None = getattr(file, "filename", None)
    if not filename or not filename.lower().endswith(".csv"):
        raise HTTPException(400, "Please upload a .csv file")

    content = await file.read()
    try:
        text = content.decode("utf-8")
    except Exception:
        raise HTTPException(400, "CSV must be UTF-8 encoded")

    reader = csv.DictReader(io.StringIO(text))

    # Verify required headers
    header_set = {(h or "").strip().lower() for h in (reader.fieldnames or [])}
    required = {"symbol", "date"}  # open/close optional
    if not required.issubset(header_set):
        raise HTTPException(400, f"CSV must include headers: {sorted(required)}")

    parsed_rows: list[PriceIn] = []
    line_no = 1  # account for header row
    for row in reader:
        line_no += 1
        symbol_raw = (row.get("symbol") or "").strip()
        date_raw = (row.get("date") or "").strip()
        open_raw = (row.get("open") or "").strip()
        close_raw = (row.get("close") or "").strip()

        if not symbol_raw:
            raise HTTPException(400, f"Row {line_no}: 'symbol' is required")
        if not date_raw:
            raise HTTPException(400, f"Row {line_no}: 'date' is required (YYYY-MM-DD)")
        try:
            d = date.fromisoformat(date_raw)
        except ValueError:
            raise HTTPException(
                400, f"Row {line_no}: invalid date '{date_raw}' (expected YYYY-MM-DD)"
            )

        def to_float(s: str) -> float | None:
            if s == "":
                return None
            try:
                return float(s)
            except ValueError:
                raise HTTPException(400, f"Row {line_no}: invalid number '{s}'")

        open_val = to_float(open_raw)
        close_val = to_float(close_raw)

        # Build a PriceIn with a REAL date (keeps type-checkers happy)
        parsed_rows.append(PriceIn(symbol=symbol_raw, date=d, open=open_val, close=close_val))

    ins, upd = _upsert_prices(db, parsed_rows)
    return {"inserted": ins, "updated": upd}
