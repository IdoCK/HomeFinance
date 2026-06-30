"""Import router — thin wrapper over the local-agent parser + the DB.

Parsing runs entirely on-machine (Ollama via agent_parser); nothing leaves the
box. The flow is split so the UI can review before committing: /parse returns
candidate rows, /commit writes them. Files are de-duplicated per person by a
content hash so the same export can't be imported twice.
"""
import hashlib
from datetime import datetime

from typing import Optional

from fastapi import APIRouter, File, Form, Query, UploadFile

from modules import database as db
from modules import parsing
from modules import agent_parser
from modules import formats
from backend.schemas import ImportCommit

router = APIRouter(prefix="/import", tags=["import"])


def _category_rules(person_id: int):
    # Global taxonomy: every category's keyword rules apply to every import,
    # regardless of which person the file is imported for.
    return [(c["name"], (c["keywords"] or "").split(","))
            for c in db.get_categories()]


@router.get("/untracked-count")
def untracked_count(person_id: Optional[int] = Query(None)):
    """Return the count of transactions with no file_hash (legacy/untracked rows).

    person_id omitted (None) = household view: counts across all people.
    """
    return {"count": db.count_untracked_transactions(person_id)}


@router.get("/status")
def status():
    ok, message = agent_parser.check_ollama()
    return {"ok": ok, "message": message}


@router.post("/parse")
def parse(file: UploadFile = File(...), source: str = Form("auto"),
          person_id: int = Form(...), currency: str = Form("auto")):
    raw = file.file.read()
    file_hash = hashlib.sha256(raw).hexdigest()
    if db.get_import(person_id, file_hash):
        return {"already_imported": True, "file_hash": file_hash,
                "filename": file.filename, "source": source, "rows": [], "warnings": []}

    file_default = None if currency == "auto" else currency
    rules = _category_rules(person_id)
    raw_df = agent_parser._read_raw_table(raw, file.filename)
    fmts = formats.load_formats()
    fmt, header_row = formats.match_format(
        raw_df, raw.decode("utf-8-sig", errors="replace"), fmts) if not raw_df.empty else (None, None)

    warnings = []
    if fmt is not None:
        # Registry-first: known layout parses deterministically; default_currency
        # applies. Upload default overrides the registry default when given.
        if file_default:
            fmt = {**fmt, "parse": {**fmt.get("parse", {}), "default_currency": file_default}}
        rows, skipped, _ = formats.parse_with_format(
            raw_df, fmt, header_row, source, parsing.categorize, rules)
        if skipped:
            warnings.append(f"{file.filename}: skipped {skipped} unparseable row(s).")
    else:
        rows, warnings = agent_parser.parse_file_with_agent(
            raw, file.filename, source, parsing.categorize, rules, file_default=file_default)

    unknown = sum(1 for r in rows if r.get("currency_source") == "unknown")
    if unknown:
        warnings.append(f"{file.filename}: {unknown} row(s) need a currency before import.")
    return {"already_imported": False, "file_hash": file_hash,
            "filename": file.filename, "source": source, "rows": rows, "warnings": warnings}


@router.post("/commit")
def commit(body: ImportCommit):
    from modules import fx
    rows = [r.model_dump() for r in body.rows]
    fx.resolve_rows(rows)  # fills amount_base (USD) per row's date+currency
    db.add_transactions(body.person_id, rows, file_hash=body.file_hash)
    db.record_import(body.person_id, body.file_hash, body.filename, len(rows),
                     datetime.now().strftime("%Y-%m-%d %H:%M"))
    return {"imported": len(rows)}
