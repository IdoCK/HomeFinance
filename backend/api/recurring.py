from typing import Optional

from fastapi import APIRouter

from modules import database as db
from modules import analytics

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
def list_recurring(person_id: Optional[int] = None):
    recurring = analytics.recurring_charges(
        db.get_transactions(person_id), _vendor_rules(person_id)
    )
    return {
        "charges": recurring,
        "committed": analytics.committed_monthly(recurring),
        "anomalies": analytics.recurring_anomalies(recurring),
    }
