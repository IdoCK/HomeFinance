from fastapi import APIRouter

from modules import database as db
from backend.schemas import CategoryUpsert

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
def list_categories(person_id: int):
    return db.get_categories()


@router.put("")
def upsert_category(body: CategoryUpsert):
    db.upsert_category(body.name, body.keywords, body.parent)
    return {"ok": True}


@router.delete("/{category_id}")
def remove_category(category_id: int):
    db.delete_category(category_id)
    return {"ok": True}
