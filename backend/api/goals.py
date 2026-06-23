from typing import Optional

from fastapi import APIRouter

from modules import database as db
from modules import analytics
from modules import fx
from backend.schemas import GoalCreate, GoalSavedUpdate, GoalNotesUpdate

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("")
def list_goals(person_id: Optional[int] = None, display: str = "USD"):
    """person_id omitted -> Joint -> all goals (everyone's + shared)."""
    goals = db.get_goals(person_id if person_id is not None else "all")

    # Derive the household's average monthly savings in USD (base currency) so
    # goal_progress can compute pace status and projected completion.
    # fx.base_txns converts each transaction's amount to the USD pivot so
    # analytics.monthly_savings sums one currency across all accounts.
    txns = fx.base_txns(db.get_transactions(person_id if person_id is not None else None))
    savings_df = analytics.monthly_savings(txns)
    avg_monthly_savings: Optional[float] = None
    if not savings_df.empty and "savings" in savings_df.columns:
        complete = savings_df[savings_df.get("complete", False)] if "complete" in savings_df.columns else savings_df
        if not complete.empty:
            avg_monthly_savings = float(complete["savings"].mean())
        else:
            avg_monthly_savings = float(savings_df["savings"].mean())

    out = analytics.goal_progress(goals, actual_monthly_savings=avg_monthly_savings)

    f = fx.display_factor(display) or 1.0
    if f != 1.0:
        # Scale money fields; leave status (str) and projected_completion (date str) untouched.
        keys = ("target_amount", "saved_amount", "monthly_needed")
        out = [{**g, **{k: (None if g.get(k) is None else round(g[k] * f, 2)) for k in keys}} for g in out]
    return out


@router.post("")
def create_goal(body: GoalCreate):
    db.add_goal(body.person_id, body.name, body.target_amount, body.saved_amount,
                body.target_date, body.horizon, body.notes, body.currency)
    return {"ok": True}


@router.patch("/{goal_id}")
def update_goal(goal_id: int, body: GoalSavedUpdate):
    db.update_goal_saved(goal_id, body.saved_amount)
    return {"ok": True}


@router.patch("/{goal_id}/notes")
def update_goal_notes(goal_id: int, body: GoalNotesUpdate):
    db.update_goal_notes(goal_id, body.notes)
    return {"ok": True}


@router.delete("/{goal_id}")
def remove_goal(goal_id: int):
    db.delete_goal(goal_id)
    return {"ok": True}
