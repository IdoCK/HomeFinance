from fastapi import APIRouter, HTTPException

from modules import database as db
from app.schemas import PersonUpdate

router = APIRouter(prefix="/people", tags=["people"])


@router.get("")
def list_people():
    return db.list_people()


@router.patch("/{person_id}")
def rename_person(person_id: int, body: PersonUpdate):
    if not any(p["id"] == person_id for p in db.list_people()):
        raise HTTPException(status_code=404, detail="person not found")
    db.rename_person(person_id, body.name)
    return {"id": person_id, "name": body.name}
