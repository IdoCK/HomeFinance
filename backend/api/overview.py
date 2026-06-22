from typing import Optional

import pandas as pd
from fastapi import APIRouter

from modules import database as db
from modules import analytics

router = APIRouter(prefix="/overview", tags=["overview"])


def _empty():
    return {"month": None, "months": [], "income": 0.0, "spend": 0.0, "net": 0.0,
            "savings_rate": None, "complete": False, "by_category": {},
            "alerts": [], "series": [], "split": None}


@router.get("")
def overview(person_id: Optional[int] = None, month: Optional[str] = None):
    txns = db.get_transactions(person_id)
    sav = analytics.monthly_savings(txns)
    if sav.empty:
        return _empty()

    recs = {}
    for idx, row in sav.iterrows():
        rate = row["savings_rate"]
        recs[str(idx)] = {
            "income": float(row["income"]),
            "spend": float(row["spend"]),
            "net": float(row["savings"]),
            "savings_rate": None if pd.isna(rate) else float(rate),
            "complete": bool(row["complete"]),
        }

    months = list(recs.keys())
    if month is None or month not in recs:
        latest = analytics.latest_complete_month(sav)
        month = str(latest) if latest is not None else months[-1]

    month_txns = [t for t in txns if (t.get("date") or "")[:7] == month]
    sel = recs[month]

    # Per-month trend for the cash-flow area + savings-rate bars (months order).
    series = [{"month": m, **recs[m]} for m in months]

    # Joint-only per-person spend split for the "who spent what" dot-matrix.
    # Only meaningful when no single person is selected; a single-persona view
    # uses by_category instead (frontend). Spend nets refunds via category_totals.
    split = None
    if person_id is None:
        split = []
        for p in db.list_people():
            p_txns = [t for t in month_txns if t.get("person_id") == p["id"]]
            spend = sum(analytics.category_totals(p_txns).values())
            split.append({"person_id": p["id"], "name": p["name"], "spend": float(spend)})

    return {
        "month": month,
        "months": months,
        "income": sel["income"],
        "spend": sel["spend"],
        "net": sel["net"],
        "savings_rate": sel["savings_rate"],
        "complete": sel["complete"],
        "by_category": analytics.category_totals(month_txns),
        "alerts": analytics.spending_alerts(txns),
        "series": series,
        "split": split,
    }
