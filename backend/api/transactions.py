from typing import Optional

from fastapi import APIRouter, HTTPException

from modules import database as db
from modules import analytics
from modules import fx
from backend.schemas import TransactionUpdate

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("")
def list_transactions(person_id: Optional[int] = None, display: str = "USD"):
    """person_id omitted -> all people (Joint). `display` re-expresses each row at
    its own transaction-date rate; the original amount+currency are preserved."""
    rows = db.get_transactions(person_id)
    # Map each row's file_hash to the imported file's display name, so the UI can
    # filter by source file. Legacy rows (no file_hash) get filename=None.
    names = {(im["person_id"], im["file_hash"]): im["filename"]
             for im in db.list_imports(person_id)}
    for t in rows:
        base = t.get("amount_base")
        base = t.get("amount") if base is None else base
        conv = fx.convert(base, display, t.get("date"))
        t["original_amount"] = t.get("amount")
        t["original_currency"] = t.get("currency", "USD")
        t["amount_base"] = base
        t["rate_stale"] = conv is None
        t["amount"] = base if conv is None else conv   # never show a wrong/zero number
        t["filename"] = names.get((t.get("person_id"), t.get("file_hash")))
    return rows


@router.get("/transfers")
def transfer_pairs(person_id: Optional[int] = None):
    """Detected internal-transfer pairs (an outflow matched to an equal inflow).
    Joint (person_id omitted) catches cross-person moves; a person scope catches
    their own-account transfers. The UI can exclude both sides of a pair.

    Matching is currency-aware via `amount_base` (USD pivot) on each transaction
    row — a ₪370 outflow will not pair with a $370 inflow. Each pair dict carries
    `out_currency`, `in_currency`, `out_amount`, and `in_amount` for the UI."""
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
