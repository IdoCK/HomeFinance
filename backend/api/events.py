"""Events router — tag transactions to named events (trips, projects, etc.).

Thin wrapper over the engine's event CRUD + tag membership. Each listed event
carries its tagged-transaction count and net total so the UI can show event
spend at a glance. v1 supports explicit membership; rule-based auto-membership
(engine `rule`/`event_mask`) is deferred.
"""
from typing import Optional

from fastapi import APIRouter

from modules import database as db
from modules import fx
from backend.schemas import EventCreate, EventTags

router = APIRouter(prefix="/events", tags=["events"])


def _scope(person_id: Optional[int]):
    """Persona -> engine scope: a person id (their events + household), or 'all' for Joint."""
    return person_id if person_id is not None else "all"


@router.get("")
def list_events(person_id: Optional[int] = None, display: str = "USD"):
    events = db.list_events(_scope(person_id))
    # Totals computed in USD base then scaled to the display currency, so the
    # figures track the global currency toggle like every other page.
    f = fx.display_factor(display) or 1.0
    amounts = {t["id"]: t["amount"] for t in fx.base_txns(db.get_transactions())}
    out = []
    for e in events:
        ids = db.event_transaction_ids(e["id"])
        total = round(sum(amounts.get(i, 0.0) for i in ids) * f, 2)
        out.append({**e, "txn_count": len(ids), "total": total})
    return out


@router.post("")
def create_event(body: EventCreate):
    eid = db.create_event(body.person_id, body.name, body.kind,
                          body.start_date, body.end_date, body.rule)
    return {"id": eid}


@router.delete("/{event_id}")
def remove_event(event_id: int):
    db.delete_event(event_id)
    return {"ok": True}


@router.get("/{event_id}/transactions")
def event_transactions(event_id: int):
    return db.event_transaction_ids(event_id)


@router.put("/{event_id}/transactions")
def set_event_transactions(event_id: int, body: EventTags):
    db.set_event_tags(event_id, body.transaction_ids)
    return {"ok": True}
