from typing import Optional

from fastapi import APIRouter, HTTPException

from modules import database as db
from modules import analytics
from backend.schemas import TransactionUpdate

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("")
def list_transactions(person_id: Optional[int] = None):
    """person_id omitted -> all people (Joint)."""
    return db.get_transactions(person_id)


@router.get("/transfers")
def transfer_pairs(person_id: Optional[int] = None):
    """Detected internal-transfer pairs (an outflow matched to an equal inflow).
    Joint (person_id omitted) catches cross-person moves; a person scope catches
    their own-account transfers. The UI can exclude both sides of a pair."""
    return analytics.find_transfer_pairs(db.get_transactions(person_id))


@router.patch("/{txn_id}")
def update_transaction(txn_id: int, body: TransactionUpdate):
    rows = db.get_transactions()
    if not any(t["id"] == txn_id for t in rows):
        raise HTTPException(status_code=404, detail="transaction not found")
    if body.category is not None:
        db.set_transaction_category(txn_id, body.category)
    if body.included is not None:
        db.set_transaction_included(txn_id, body.included)
    return next(t for t in db.get_transactions() if t["id"] == txn_id)
