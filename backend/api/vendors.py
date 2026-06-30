from fastapi import APIRouter

from modules import database as db
from backend.schemas import VendorUpsert, VendorGroup

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.get("")
def list_vendors(person_id: int):
    return db.get_vendors()


@router.put("")
def upsert_vendor(body: VendorUpsert):
    db.upsert_vendor(body.name, body.keywords)
    return {"ok": True}


@router.post("/group")
def group_vendor(body: VendorGroup):
    """Fold a dragged merchant key into a vendor group (drill-down drag-to-group).
    The merchant collapses under `target` in every vendor view from now on."""
    keywords = db.group_vendor(body.target, body.keyword)
    return {"ok": True, "name": body.target, "keywords": keywords}


@router.post("/ungroup")
def ungroup_vendor(body: VendorGroup):
    """Remove a merchant `keyword` from vendor group `target` (drill-down
    remove-a-member). Deletes the rule when its last keyword is removed."""
    keywords = db.ungroup_vendor(body.target, body.keyword)
    return {"ok": True, "name": body.target, "keywords": keywords}


@router.delete("/{vendor_id}")
def remove_vendor(vendor_id: int):
    db.delete_vendor(vendor_id)
    return {"ok": True}
