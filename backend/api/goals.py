from typing import Optional

from fastapi import APIRouter

from modules import database as db
from modules import analytics
from modules import fx
from backend.schemas import GoalCreate, GoalSavedUpdate

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("")
def list_goals(person_id: Optional[int] = None, display: str = "USD"):
    """person_id omitted -> Joint -> all goals (everyone's + shared)."""
    goals = db.get_goals(person_id if person_id is not None else "all")
    out = analytics.goal_progress(goals)
    f = fx.display_factor(display) or 1.0
    if f != 1.0:
        keys = ("target_amount", "saved_amount", "monthly_needed")
        out = [{**g, **{k: (None if g.get(k) is None else round(g[k] * f, 2)) for k in keys}} for g in out]
    return out


@router.post("")
def create_goal(body: GoalCreate):
    db.add_goal(body.person_id, body.name, body.target_amount, body.saved_amount,
                body.target_date, body.horizon, body.notes)
    return {"ok": True}


@router.patch("/{goal_id}")
def update_goal(goal_id: int, body: GoalSavedUpdate):
    db.update_goal_saved(goal_id, body.saved_amount)
    return {"ok": True}


@router.delete("/{goal_id}")
def remove_goal(goal_id: int):
    db.delete_goal(goal_id)
    return {"ok": True}
