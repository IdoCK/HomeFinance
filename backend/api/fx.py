from fastapi import APIRouter

from modules import database as db
from modules import fx as fxmod
from backend.schemas import FxRateUpsert, FxRefresh

router = APIRouter(prefix="/fx", tags=["fx"])


@router.get("/rates")
def list_rates():
    with db.get_conn() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT rate_date, base, quote, rate, source, fetched_at "
            "FROM fx_rates ORDER BY rate_date DESC")]
    last = next((r["fetched_at"] for r in rows if r["fetched_at"]), None)
    src = rows[0]["source"] if rows else None
    return {"source": src, "last_fetched": last, "count": len(rows), "rates": rows}


@router.put("/rates")
def upsert_rate(body: FxRateUpsert):
    fxmod.upsert_rate(body.rate_date, body.base, body.quote, body.rate, source="manual")
    return {"ok": True}


@router.post("/refresh")
def refresh(body: FxRefresh):
    """Explicit, user-initiated fetch. Sends only date+currency pair per date.
    After fetching, immediately recomputes amount_base for all stale rows so
    freshly-fetched rates backfill the ledger without a separate call."""
    fetched = failed = 0
    for d in body.dates:
        if fxmod.fetch_rate(d, body.base, body.quote) is not None:
            fetched += 1
        else:
            failed += 1
    updated, stale = db.recompute_amount_base()
    return {"fetched": fetched, "failed": failed,
            "recomputed": {"updated": updated, "stale": stale}}


@router.post("/recompute")
def recompute():
    updated, stale = db.recompute_amount_base()
    return {"updated": updated, "stale": stale}
