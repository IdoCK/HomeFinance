from typing import Optional

from fastapi import APIRouter

from modules import database as db

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("")
def list_transactions(person_id: Optional[int] = None):
    """person_id omitted -> all people (Joint)."""
    return db.get_transactions(person_id)
