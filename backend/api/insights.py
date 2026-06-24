"""AI Insights router — thin wrapper over modules/ai_insights.py.

Only anonymized aggregates ever leave the machine (see modules/ai_insights.py).
The persona maps to who gets summarized: an int person_id => that one person
("Person A"); omitted (Joint) => the whole household (Person A/B + shared goals).
"""
from typing import Optional

from fastapi import APIRouter

from modules import database as db
from modules import analytics
from modules import ai_insights
from modules import fx
from backend.schemas import InsightsRequest

router = APIRouter(prefix="/insights", tags=["insights"])


def _summaries(person_id: Optional[int]):
    """Build the anonymized summary list for the active persona."""
    if person_id is not None:
        txns = fx.base_txns(db.get_transactions(person_id))  # summarize in USD base
        goals = db.get_goals(person_id)
        return [ai_insights.build_anonymized_summary("Person A", txns, goals, analytics)]

    # Joint => household: one summary per person, then a shared-goals household summary.
    summaries = []
    for i, p in enumerate(db.list_people()):
        label = f"Person {chr(65 + i)}"  # Person A, Person B, ...
        summaries.append(ai_insights.build_anonymized_summary(
            label, fx.base_txns(db.get_transactions(p["id"])), db.get_goals(p["id"]), analytics))
    summaries.append(ai_insights.build_anonymized_summary(
        "Household (shared goals)", fx.base_txns(db.get_transactions()), db.get_goals(None), analytics))
    return summaries


@router.get("/preview")
def preview(person_id: Optional[int] = None):
    import os
    summaries = _summaries(person_id)
    return {
        "payload": ai_insights.preview_payload(summaries),
        "has_key": bool(os.environ.get("ANTHROPIC_API_KEY")),
    }


@router.post("/generate")
def generate(body: InsightsRequest):
    summaries = _summaries(body.person_id)
    return {"text": ai_insights.get_insights(summaries)}
