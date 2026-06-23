from typing import Optional

from fastapi import APIRouter

from modules import database as db
from modules import analytics
from modules import fx

router = APIRouter(prefix="/recurring", tags=["recurring"])


def _vendor_rules(person_id: Optional[int]):
    """db.get_vendors dicts -> the (name, [keywords]) tuples vendor_of expects.
    None for Joint (vendor rules are per-person)."""
    if person_id is None:
        return None
    return [
        (v["name"], [k.strip() for k in (v["keywords"] or "").split(",") if k.strip()])
        for v in db.get_vendors(person_id)
    ]


@router.get("")
def list_recurring(person_id: Optional[int] = None, display: str = "USD"):
    recurring = analytics.recurring_charges(
        fx.base_txns(db.get_transactions(person_id)), _vendor_rules(person_id)
    )
    committed = analytics.committed_monthly(recurring)
    anomalies = analytics.recurring_anomalies(recurring)
    charges = recurring
    f = fx.display_factor(display) or 1.0
    if f != 1.0:
        ck = ("typical_amount", "prior_typical", "last_amount", "monthly_cost", "annual_cost")
        charges = [{**c, **{k: round(c[k] * f, 2) for k in ck if c.get(k) is not None}}
                   for c in recurring]
        committed = {k: round(v * f, 2) for k, v in committed.items()}
    return {
        "charges": charges,
        "committed": committed,
        "anomalies": anomalies,
    }
