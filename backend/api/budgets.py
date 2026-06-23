import datetime
from typing import Optional

from fastapi import APIRouter

from modules import database as db
from modules import analytics
from modules import fx
from backend.schemas import BudgetUpsert

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("")
def list_budgets(person_id: Optional[int] = None, display: str = "USD"):
    """person_id omitted -> household budgets (person_id IS NULL) vs everyone's spend."""
    txns = fx.base_txns(db.get_transactions(person_id))
    budgets = db.get_budgets(person_id)
    parents = db.category_parents(person_id) if person_id is not None else {}

    # Convert each budget's amount from its stored currency to USD so that
    # analytics.budget_status compares like-for-like against USD-base txns.
    # We use today's date for the rate lookup (budgets are recurring monthly caps).
    # If the rate is unavailable (to_base returns None), degrade gracefully:
    # keep the original amount as the cap (non-zero, visible) and mark
    # rate_stale=True so the UI can warn.  Mirrors the resolve_rows convention
    # in modules/fx.py.  USD budgets always pass through unchanged.
    today = datetime.date.today().isoformat()
    budgets_usd = []
    for b in budgets:
        currency = b.get("currency") or "USD"
        amount = b.get("amount")
        if amount is None:
            budgets_usd.append({**b})
            continue
        amount_usd = fx.to_base(amount, currency, today)
        if amount_usd is None:
            # Rate unavailable — keep original amount so cap stays non-zero;
            # flag stale so the UI/caller can display a warning.
            budgets_usd.append({**b, "amount": amount, "rate_stale": True})
        else:
            budgets_usd.append({**b, "amount": amount_usd})

    rows = analytics.budget_status(txns, budgets_usd, parents)
    f = fx.display_factor(display) or 1.0
    if f == 1.0:
        return rows
    money = ("spent", "budget", "amount", "expected_to_date", "projected_eom")
    return [{**r, **{k: round(r[k] * f, 2) for k in money if k in r and r[k] is not None}} for r in rows]


@router.put("")
def upsert_budget(body: BudgetUpsert):
    db.set_budget(body.person_id, body.category, body.amount, body.currency)
    return {"ok": True}


@router.delete("/{budget_id}")
def remove_budget(budget_id: int):
    db.delete_budget(budget_id)
    return {"ok": True}
