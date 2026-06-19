from typing import Optional

from fastapi import APIRouter

from modules import database as db
from modules import analytics
from backend.schemas import BudgetUpsert

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("")
def list_budgets(person_id: Optional[int] = None):
    """person_id omitted -> household budgets (person_id IS NULL) vs everyone's spend."""
    txns = db.get_transactions(person_id)
    budgets = db.get_budgets(person_id)
    parents = db.category_parents(person_id) if person_id is not None else {}
    return analytics.budget_status(txns, budgets, parents)


@router.put("")
def upsert_budget(body: BudgetUpsert):
    db.set_budget(body.person_id, body.category, body.amount)
    return {"ok": True}


@router.delete("/{budget_id}")
def remove_budget(budget_id: int):
    db.delete_budget(budget_id)
    return {"ok": True}
