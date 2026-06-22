"""Import router — thin wrapper over the local-agent parser + the DB.

Parsing runs entirely on-machine (Ollama via agent_parser); nothing leaves the
box. The flow is split so the UI can review before committing: /parse returns
candidate rows, /commit writes them. Files are de-duplicated per person by a
content hash so the same export can't be imported twice.
"""
import hashlib
from datetime import datetime

from fastapi import APIRouter, File, Form, UploadFile

from modules import database as db
from modules import parsing
from modules import agent_parser
from backend.schemas import ImportCommit

router = APIRouter(prefix="/import", tags=["import"])


def _category_rules(person_id: int):
    return [(c["name"], (c["keywords"] or "").split(","))
            for c in db.get_categories(person_id)]


@router.get("/status")
def status():
    ok, message = agent_parser.check_ollama()
    return {"ok": ok, "message": message}


@router.post("/parse")
def parse(file: UploadFile = File(...), source: str = Form("auto"),
          person_id: int = Form(...)):
    raw = file.file.read()
    file_hash = hashlib.sha256(raw).hexdigest()
    if db.get_import(person_id, file_hash):
        return {"already_imported": True, "file_hash": file_hash,
                "filename": file.filename, "source": source, "rows": [], "warnings": []}
    rows, warnings = agent_parser.parse_file_with_agent(
        raw, file.filename, source, parsing.categorize, _category_rules(person_id))
    return {"already_imported": False, "file_hash": file_hash,
            "filename": file.filename, "source": source,
            "rows": rows, "warnings": warnings}


@router.post("/commit")
def commit(body: ImportCommit):
    rows = [r.model_dump() for r in body.rows]
    db.add_transactions(body.person_id, rows, file_hash=body.file_hash)
    db.record_import(body.person_id, body.file_hash, body.filename, len(rows),
                     datetime.now().strftime("%Y-%m-%d %H:%M"))
    return {"imported": len(rows)}
