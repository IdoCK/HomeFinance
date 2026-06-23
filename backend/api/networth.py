from datetime import date as _date
from typing import Optional

from fastapi import APIRouter, HTTPException

from modules import database as db
from modules import analytics
from modules import fx
from backend.schemas import (
    AccountCreate, AccountBalanceUpdate, AccountSnapshotCreate, PopulateFromStatements,
)

router = APIRouter(prefix="/networth", tags=["networth"])


def _scope(person_id: Optional[int]):
    """Persona -> engine scope: a real person id, or 'all' for Joint."""
    return person_id if person_id is not None else "all"


def _accounts_to_base(accounts):
    """Copies with balance converted to USD via each account's own currency
    (current balances -> today's rate). Adds original_balance + currency."""
    today = _date.today().isoformat()
    out = []
    for a in accounts:
        ccy = a.get("currency", "USD")
        base = a["balance"] if ccy == "USD" else (fx.to_base(a["balance"], ccy, today) or a["balance"])
        out.append({**a, "balance": base, "original_balance": a["balance"], "currency": ccy})
    return out


@router.get("")
def get_networth(person_id: Optional[int] = None, display: str = "USD"):
    scope = _scope(person_id)
    accounts = _accounts_to_base(db.list_accounts(scope))   # USD base
    f = fx.display_factor(display) or 1.0
    summary = analytics.net_worth(accounts)                 # USD
    summary = {k: round(v * f, 2) for k, v in summary.items()}
    trend_df = analytics.net_worth_trend(db.get_snapshots(scope))
    trend = [] if trend_df.empty else trend_df.to_dict(orient="records")
    trend = [{**p, "assets": round(p["assets"] * f, 2), "liabilities": round(p["liabilities"] * f, 2),
              "net": round(p["net"] * f, 2)} for p in trend]
    delta = round(summary["net"] - trend[-2]["net"], 2) if len(trend) >= 2 else None

    # Joint view: break net worth down by owner (shared accounts → "Shared").
    split = None
    if person_id is None:
        names = {p["id"]: p["name"] for p in db.list_people()}
        groups: dict = {}
        for a in accounts:
            groups.setdefault(a.get("person_id"), []).append(a)
        split = []
        for pid, accs in groups.items():
            s = analytics.net_worth(accs)
            split.append({
                "person_id": pid,
                "name": names.get(pid, "Shared") if pid is not None else "Shared",
                "net": round(s["net"] * f, 2), "assets": round(s["assets"] * f, 2),
                "liabilities": round(s["liabilities"] * f, 2),
            })
        split.sort(key=lambda r: r["net"], reverse=True)

    # accounts shown in display currency, originals preserved
    disp_accounts = [{**a, "balance": round(a["balance"] * f, 2)} for a in accounts]

    return {"summary": summary, "delta": delta, "accounts": disp_accounts,
            "trend": trend, "split": split}


@router.get("/reconcile")
def reconcile(person_id: Optional[int] = None):
    """Tie each bank statement out against its own running-balance column.

    Groups transactions by (person_id, file_hash) so that statements in
    different accounts or currencies are reconciled independently. Each result
    carries the statement's own currency (raw, not converted to any display
    currency). Returns { statements: [{ filename, currency, begin, end,
    computed_end, discrepancy, n, chain_breaks, ok }] }.
    """
    # Collect all import records for the scope so we can look up filenames.
    imports = db.list_imports(person_id)
    filename_by_hash: dict = {im["file_hash"]: im["filename"] for im in imports}

    # Group transactions by (person_id, file_hash) so each statement is
    # reconciled independently.
    scope_txns = db.get_transactions(person_id)
    by_statement: dict = {}
    for txn in scope_txns:
        key = (txn.get("person_id"), txn.get("file_hash"))
        by_statement.setdefault(key, []).append(txn)

    statements = []
    for (pid, fh), rows in by_statement.items():
        if fh is None:
            continue  # skip transactions with no associated import file
        # Derive the statement currency from the first row that has one.
        currency = next(
            (r.get("currency") for r in rows if r.get("currency")), "USD"
        )
        result = analytics.reconcile(rows, currency=currency)
        if result is None:
            continue  # no running-balance data — not reconcilable
        filename = filename_by_hash.get(fh, fh)
        statements.append({"filename": filename, **result})

    return {"statements": statements}


@router.get("/accounts/{account_id}/history")
def account_history(account_id: int):
    """Balance snapshots for one account, oldest first — the per-account history
    sparkline on the Net Worth page (the old per-account balance line charts)."""
    return {"snapshots": db.account_snapshots(account_id)}


@router.get("/accounts/{account_id}/imports")
def account_imports(account_id: int):
    """Imported statement files for this account's owner — the pick-list for
    populating month-end balances. Each carries filename + live row count."""
    acct = db.get_account(account_id)
    if acct is None:
        raise HTTPException(404, "Account not found")
    imports = db.list_imports(acct["person_id"])
    return {"imports": [{"file_hash": im["file_hash"], "filename": im["filename"],
                         "count": im.get("live_count", im.get("count", 0))}
                        for im in imports]}


@router.post("/accounts/{account_id}/snapshot")
def record_snapshot(account_id: int, body: AccountSnapshotCreate):
    """Record a manual balance as of a date (investments, 401k, HSA…) and make it
    the current balance — the old 'Record a balance as of a date' action."""
    if db.get_account(account_id) is None:
        raise HTTPException(404, "Account not found")
    db.update_account_balance(account_id, body.balance, snapshot_date=body.date)
    return {"ok": True}


@router.post("/accounts/{account_id}/populate-from-statements")
def populate_from_statements(account_id: int, body: PopulateFromStatements):
    """Derive month-end balances from the chosen bank statements' running-balance
    column and record them as snapshots (the old 'Populate month-end balances from
    statements'). Current balance is set to the most recent month-end. Returns the
    number of month-end points recorded; 0 means none of the files carried a
    running balance (e.g. a credit-card feed)."""
    acct = db.get_account(account_id)
    if acct is None:
        raise HTTPException(404, "Account not found")
    rows = []
    for fh in body.file_hashes:
        rows += db.transactions_for_file(acct["person_id"], fh)
    points = analytics.month_end_balances(rows)
    for pt in points:
        db.write_snapshot(account_id, pt["date"], pt["balance"])
    if points:
        last = points[-1]
        db.update_account_balance(account_id, last["balance"], snapshot_date=last["date"])
    return {"ok": True, "recorded": len(points)}


@router.post("/accounts")
def create_account(body: AccountCreate):
    aid = db.add_account(body.person_id, body.name, body.kind, body.is_asset, body.balance, body.currency)
    return {"ok": True, "id": aid}


@router.patch("/accounts/{account_id}")
def update_account(account_id: int, body: AccountBalanceUpdate):
    db.update_account_balance(account_id, body.balance)
    return {"ok": True}


@router.delete("/accounts/{account_id}")
def remove_account(account_id: int):
    db.delete_account(account_id)
    return {"ok": True}
