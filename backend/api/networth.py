from typing import Optional

from fastapi import APIRouter

from modules import database as db
from modules import analytics
from backend.schemas import AccountCreate, AccountBalanceUpdate

router = APIRouter(prefix="/networth", tags=["networth"])


def _scope(person_id: Optional[int]):
    """Persona -> engine scope: a real person id, or 'all' for Joint."""
    return person_id if person_id is not None else "all"


@router.get("")
def get_networth(person_id: Optional[int] = None):
    scope = _scope(person_id)
    accounts = db.list_accounts(scope)
    summary = analytics.net_worth(accounts)
    trend_df = analytics.net_worth_trend(db.get_snapshots(scope))
    trend = [] if trend_df.empty else trend_df.to_dict(orient="records")
    delta = round(summary["net"] - trend[-2]["net"], 2) if len(trend) >= 2 else None
    return {"summary": summary, "delta": delta, "accounts": accounts, "trend": trend}


@router.get("/reconcile")
def reconcile(person_id: Optional[int] = None):
    """Tie a person's bank statements out against their running-balance column.
    Joint (person_id omitted) reconciles all transactions together."""
    result = analytics.reconcile(db.get_transactions(person_id))
    if result is None:
        return {"reconcilable": False}
    return {"reconcilable": True, **result}


@router.post("/accounts")
def create_account(body: AccountCreate):
    aid = db.add_account(body.person_id, body.name, body.kind, body.is_asset, body.balance)
    return {"ok": True, "id": aid}


@router.patch("/accounts/{account_id}")
def update_account(account_id: int, body: AccountBalanceUpdate):
    db.update_account_balance(account_id, body.balance)
    return {"ok": True}


@router.delete("/accounts/{account_id}")
def remove_account(account_id: int):
    db.delete_account(account_id)
    return {"ok": True}
