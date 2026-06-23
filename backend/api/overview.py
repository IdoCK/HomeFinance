from typing import Optional

import pandas as pd
from fastapi import APIRouter

from modules import database as db
from modules import analytics
from modules import fx

router = APIRouter(prefix="/overview", tags=["overview"])


def _empty():
    return {"month": None, "months": [], "income": 0.0, "spend": 0.0, "net": 0.0,
            "savings_rate": None, "complete": False, "by_category": {},
            "alerts": [], "series": [], "split": None,
            "uncategorized": {"count": 0, "amount": 0.0}}


def _scale(v, f):
    return v if v is None else round(v * f, 2)


@router.get("")
def overview(person_id: Optional[int] = None, month: Optional[str] = None,
             display: str = "USD"):
    txns = fx.base_txns(db.get_transactions(person_id))   # analytics in USD
    f = fx.display_factor(display) or 1.0                  # offline fallback: USD
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

    by_category = {k: _scale(v, f) for k, v in analytics.category_totals(month_txns).items()}

    # Uncategorized count: expense rows (amount < 0) whose category is Uncategorized/empty/None
    _unc_cats = {"Uncategorized", "", None}
    unc_count = sum(
        1 for t in month_txns
        if t.get("category") in _unc_cats and (t.get("amount") or 0) < 0
    )
    # Uncategorized amount: use category_totals so it is identical to by_category["Uncategorized"]
    unc_amount_base = analytics.category_totals(month_txns).get("Uncategorized", 0.0)
    unc_amount = _scale(unc_amount_base, f)

    series = [{**p, "income": _scale(p["income"], f), "spend": _scale(p["spend"], f),
               "net": _scale(p["net"], f)} for p in series]
    if split is not None:
        split = [{**s, "spend": _scale(s["spend"], f)} for s in split]
    alerts = [{**a, "current": _scale(a["current"], f), "baseline": _scale(a["baseline"], f),
               "delta": _scale(a["delta"], f)} for a in analytics.spending_alerts(txns)]
    return {
        "month": month,
        "months": months,
        "income": _scale(sel["income"], f),
        "spend": _scale(sel["spend"], f),
        "net": _scale(sel["net"], f),
        "savings_rate": sel["savings_rate"],
        "complete": sel["complete"],
        "by_category": by_category,
        "alerts": alerts,
        "series": series,
        "split": split,
        "uncategorized": {"count": unc_count, "amount": unc_amount},
    }
