from fastapi import APIRouter

from modules import database as db
from backend.schemas import VendorUpsert

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.get("")
def list_vendors(person_id: int):
    return db.get_vendors(person_id)


@router.put("")
def upsert_vendor(body: VendorUpsert):
    db.upsert_vendor(body.person_id, body.name, body.keywords)
    return {"ok": True}


@router.delete("/{vendor_id}")
def remove_vendor(vendor_id: int):
    db.delete_vendor(vendor_id)
    return {"ok": True}
