"""Analysis router — the deep-dive surface (Explore / Compare / People).

Thin wrapper over the engine's advanced analytics (analytics.filter_transactions
and friends). The keystone is filter_transactions(): every endpoint here builds a
filtered txn list from the shared query params, then runs an engine function over
it, so refund-netting and the `included` flag stay correct for free.

Persona scoping mirrors the sibling routers: a person_id scopes to that person
(plus household rows); omitted = Joint / everyone.
"""
from typing import Optional

from fastapi import APIRouter, Query

from modules import database as db
from modules import analytics

router = APIRouter(prefix="/analysis", tags=["analysis"])


def _vendor_rules(person_id: Optional[int]):
    """db.get_vendors dicts -> the (name, [keywords]) tuples vendor_of expects.
    None for Joint (vendor rules are per-person). Matches recurring.py."""
    if person_id is None:
        return None
    return [
        (v["name"], [k.strip() for k in (v["keywords"] or "").split(",") if k.strip()])
        for v in db.get_vendors(person_id)
    ]


def _event(person_id: Optional[int], event_id: Optional[int]):
    """Resolve a DB event to the dict event_mask() expects, with its tagged ids
    attached (so a window/recurring event also picks up hand-tagged stragglers).
    None when no event is selected. Built-in Workdays/Weekends are expressed via
    the `day_type` param instead, so they never reach here."""
    if event_id is None:
        return None
    scope = person_id if person_id is not None else "all"
    ev = next((e for e in db.list_events(scope) if e["id"] == event_id), None)
    if ev is None:
        return None
    return {**ev, "ids": db.event_transaction_ids(event_id)}


def _filters(*, date_from, date_to, day_type, dow, months, categories, event):
    """Assemble filter_transactions kwargs from the shared query params. Absent
    params stay absent (None = no constraint)."""
    kw: dict = {}
    if date_from or date_to:
        kw["date_range"] = (date_from, date_to)
    if day_type in ("weekday", "weekend"):
        kw["day_types"] = [day_type]
    if dow:
        kw["dow"] = dow
    if months:
        kw["months"] = months
    if categories:
        kw["categories"] = categories
    if event is not None:
        kw["event"] = event
    return kw


@router.get("/filter-options")
def filter_options(person_id: Optional[int] = None):
    """Distinct months, categories and (named) events available for this persona —
    populates the shared filter bar's selects."""
    txns = db.get_transactions(person_id)
    months = sorted({(t.get("date") or "")[:7] for t in txns if t.get("date")})
    categories = sorted({t.get("category") for t in txns if t.get("category")})
    scope = person_id if person_id is not None else "all"
    events = [{"id": e["id"], "name": e["name"], "kind": e["kind"]}
              for e in db.list_events(scope)]
    return {"months": months, "categories": categories, "events": events}


@router.get("/category-trend")
def category_trend(
    person_id: Optional[int] = None,
    rollup: bool = False,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    day_type: Optional[str] = None,
    dow: Optional[list[int]] = Query(None),
    months: Optional[list[str]] = Query(None),
    categories: Optional[list[str]] = Query(None),
    event_id: Optional[int] = None,
):
    """Spending per category over time (one series per category). `rollup` groups
    categories under their parent. Series align to the returned `months` order."""
    txns = db.get_transactions(person_id)
    kw = _filters(date_from=date_from, date_to=date_to, day_type=day_type, dow=dow,
                  months=months, categories=categories,
                  event=_event(person_id, event_id))
    if kw:
        txns = analytics.filter_transactions(txns, **kw)

    pivot = analytics.spending_by_category_over_time(txns)
    if pivot.empty:
        return {"months": [], "series": []}

    if rollup:
        parents = db.category_parents(person_id) if person_id is not None else {}
        if parents:
            pivot = pivot.rename(columns=lambda c: (parents.get(c) or "").strip() or c)
            pivot = pivot.T.groupby(level=0).sum().T

    month_labels = [str(m) for m in pivot.index]
    series = [
        {"name": str(col), "values": [float(v) for v in pivot[col].tolist()],
         "total": float(pivot[col].sum())}
        for col in pivot.columns
    ]
    # Biggest spenders first — matches the old chart's legend ordering.
    series.sort(key=lambda s: s["total"], reverse=True)
    return {"months": month_labels, "series": series}


@router.get("/drill")
def drill(
    person_id: Optional[int] = None,
    level: str = "category",
    cat: Optional[str] = None,
    vendor: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    day_type: Optional[str] = None,
    dow: Optional[list[int]] = Query(None),
    months: Optional[list[str]] = Query(None),
    categories: Optional[list[str]] = Query(None),
    event_id: Optional[int] = None,
):
    """Drill one hierarchy level of spend (the old Explore drill-down):
    'category' -> ranked categories; 'vendor' (needs cat) -> ranked vendors within
    that category (merchant variants collapsed by the persona's vendor rules);
    'rows' (needs cat + vendor) -> the underlying transactions.
    Returns {level, items:[{name,value}], rows:[...]} — items for category/vendor,
    rows for the leaf."""
    txns = db.get_transactions(person_id)
    kw = _filters(date_from=date_from, date_to=date_to, day_type=day_type, dow=dow,
                  months=months, categories=categories,
                  event=_event(person_id, event_id))
    if kw:
        txns = analytics.filter_transactions(txns, **kw)
    rules = _vendor_rules(person_id)

    if level == "rows":
        cat_txns = [t for t in txns if t.get("category") == cat]
        rows = analytics.drill(cat_txns, "rows", parent=vendor, vendor_rules=rules)
        rows = [{"date": t.get("date"), "description": t.get("description"),
                 "amount": float(t.get("amount") or 0.0), "category": t.get("category")}
                for t in rows]
        rows.sort(key=lambda r: r["date"] or "", reverse=True)
        return {"level": "rows", "items": [], "rows": rows}

    if level == "vendor":
        data = analytics.drill(txns, "vendor", parent=cat, vendor_rules=rules)
    else:
        level = "category"
        data = analytics.drill(txns, "category")

    items = [{"name": str(k), "value": float(v)} for k, v in data.items()]
    return {"level": level, "items": items, "rows": []}


@router.get("/compare")
def compare(
    person_id: Optional[int] = None,
    preset: str = "weekdays_weekends",
    metric: str = "spend",
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    day_type: Optional[str] = None,
    dow: Optional[list[int]] = Query(None),
    months: Optional[list[str]] = Query(None),
    categories: Optional[list[str]] = Query(None),
    event_id: Optional[int] = None,
):
    """Two-bucket spend comparison (the old Compare tab). `preset` picks the split:
    'weekdays_weekends' or 'month_vs_month' (the two most recent months in range).
    `metric` selects the surfaced value — 'spend' (bucket totals) or 'per_day'
    (totals over the bucket's matching calendar-day count, making unequal windows
    comparable). The shared filter bar narrows the universe first; the preset then
    splits that into bucket A vs B. Returns grouped-bar-ready data:
    {buckets:[{label,total,per_day,n_days}×2], labels:{a,b}, categories:[{name,a,b}]}."""
    txns = db.get_transactions(person_id)
    kw = _filters(date_from=date_from, date_to=date_to, day_type=day_type, dow=dow,
                  months=months, categories=categories,
                  event=_event(person_id, event_id))
    if kw:
        txns = analytics.filter_transactions(txns, **kw)

    if preset == "month_vs_month":
        present = sorted({(t.get("date") or "")[:7] for t in txns if t.get("date")})
        latest = present[-1] if present else None
        prev = present[-2] if len(present) >= 2 else None
        group_a = {"label": latest or "—", "months": [latest] if latest else ["—"]}
        group_b = {"label": prev or "—", "months": [prev] if prev else ["—"]}
    else:
        preset = "weekdays_weekends"
        group_a = {"label": "Weekdays", "day_types": ["weekday"]}
        group_b = {"label": "Weekends", "day_types": ["weekend"]}

    df = analytics.compare(txns, group_a, group_b, metric="spend")
    records = [] if df.empty else df.to_dict("records")
    val_key = "per_day" if metric == "per_day" else "total"

    buckets = []
    for g in (group_a, group_b):
        rows = [r for r in records if r["bucket"] == g["label"]]
        total = float(sum(r["total"] for r in rows))
        n_days = int(rows[0]["n_days"]) if rows else 0
        buckets.append({"label": g["label"], "total": round(total, 2),
                        "per_day": round(total / n_days, 2) if n_days else 0.0,
                        "n_days": n_days})

    cats: dict = {}
    for r in records:
        c = cats.setdefault(r["category"], {"name": r["category"], "a": 0.0, "b": 0.0, "combined": 0.0})
        c["a" if r["bucket"] == group_a["label"] else "b"] = float(r[val_key])
        c["combined"] += float(r["total"])
    ranked = sorted(cats.values(), key=lambda c: c["combined"], reverse=True)
    categories = [{"name": c["name"], "a": round(c["a"], 2), "b": round(c["b"], 2)} for c in ranked]

    return {"preset": preset, "metric": metric, "buckets": buckets,
            "labels": {"a": group_a["label"], "b": group_b["label"]},
            "categories": categories}


@router.get("/overlap")
def overlap(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    day_type: Optional[str] = None,
    dow: Optional[list[int]] = Query(None),
    months: Optional[list[str]] = Query(None),
    categories: Optional[list[str]] = Query(None),
    event_id: Optional[int] = None,
):
    """Per-category spend for the two people side by side (the old People tab).
    Inherently household-wide — there is no person_id scope — so it's gated to the
    Joint view in the UI. Returns each person's total spend / category count, the
    count of mutually-spent categories, and the per-category rows (a/b spend, the
    a−b diff that drives the diverging tornado bar, and a `shared` flag)."""
    people = db.list_people()
    if len(people) < 2:
        return {"available": False, "a": None, "b": None, "shared": 0, "rows": []}
    a_p, b_p = people[0], people[1]

    txns = db.get_transactions(None)  # household; overlap is never person-scoped
    kw = _filters(date_from=date_from, date_to=date_to, day_type=day_type, dow=dow,
                  months=months, categories=categories,
                  event=_event(None, event_id))
    if kw:
        txns = analytics.filter_transactions(txns, **kw)

    rows = analytics.user_overlap(txns, a_p["id"], b_p["id"])
    a_spend = sum(r["a_spend"] for r in rows)
    b_spend = sum(r["b_spend"] for r in rows)
    return {
        "available": True,
        "a": {"id": a_p["id"], "name": a_p["name"], "spend": round(a_spend, 2),
              "categories": sum(1 for r in rows if r["a_spend"] > 0)},
        "b": {"id": b_p["id"], "name": b_p["name"], "spend": round(b_spend, 2),
              "categories": sum(1 for r in rows if r["b_spend"] > 0)},
        "shared": sum(1 for r in rows if r["shared"]),
        "rows": [{"category": r["category"], "a": round(r["a_spend"], 2),
                  "b": round(r["b_spend"], 2), "diff": round(r["diff"], 2),
                  "shared": r["shared"]}
                 for r in rows],
    }
