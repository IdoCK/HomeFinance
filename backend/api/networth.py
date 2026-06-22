from typing import Optional

from fastapi import APIRouter

from datetime import date as _date

from modules import database as db
from modules import analytics
from modules import fx
from backend.schemas import AccountCreate, AccountBalanceUpdate

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
