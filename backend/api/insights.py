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


def _summaries_and_names(person_id: Optional[int]):
    """Anonymized summaries for the active persona, plus a {label: real-name} map.

    The model only ever sees the generic labels ("Person A"/"Person B"). The map
    lets us re-personalize the model's OUTPUT locally (see ai_insights.apply_names)
    so the user reads "Ido" while real names never leave the machine.
    """
    people = db.list_people()
    if person_id is not None:
        name = next((p["name"] for p in people if p["id"] == person_id), "You")
        txns = fx.base_txns(db.get_transactions(person_id))  # summarize in USD base
        goals = db.get_goals(person_id)
        return ([ai_insights.build_anonymized_summary("Person A", txns, goals, analytics)],
                {"Person A": name})

    # Joint => household: one summary per person, then a shared-goals household summary.
    summaries, names = [], {}
    for i, p in enumerate(people):
        label = f"Person {chr(65 + i)}"  # Person A, Person B, ...
        names[label] = p["name"]
        summaries.append(ai_insights.build_anonymized_summary(
            label, fx.base_txns(db.get_transactions(p["id"])), db.get_goals(p["id"]), analytics))
    summaries.append(ai_insights.build_anonymized_summary(
        "Household (shared goals)", fx.base_txns(db.get_transactions()), db.get_goals(None), analytics))
    return summaries, names


def _summaries(person_id: Optional[int]):
    """Just the anonymized summary list (used by the privacy preview)."""
    return _summaries_and_names(person_id)[0]


@router.get("/preview")
def preview(person_id: Optional[int] = None):
    summaries = _summaries(person_id)
    return {
        "payload": ai_insights.preview_payload(summaries),
        "available": ai_insights.ai_available(),
    }


@router.post("/generate")
def generate(body: InsightsRequest):
    summaries, names = _summaries_and_names(body.person_id)
    text = ai_insights.get_insights(summaries)  # model sees only generic labels
    return {"text": ai_insights.apply_names(text, names)}  # real names re-applied locally
