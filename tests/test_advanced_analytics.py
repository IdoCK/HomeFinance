"""Tests for budgets, parent rollups, and the advanced-analytics engine
(temporal filtering, comparison, drill-down, people). All assertions derive
expectations from the data so they're calendar-independent."""

import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import analytics


def _t(i, d, amount, category, source="credit_card", person_id=1, included=1):
    return {"id": i, "date": d, "description": f"{category} {i}", "amount": amount,
            "category": category, "source": source, "person_id": person_id,
            "included": included}


# A full calendar week 2026-06-01..06-07 plus a couple extra rows.
TXNS = [
    _t(1, "2026-06-01", -100, "Groceries"),
    _t(2, "2026-06-02", -20, "Transit"),
    _t(3, "2026-06-05", -50, "Eating Out"),
    _t(4, "2026-06-06", -80, "Eating Out"),          # weekend
    _t(5, "2026-06-07", -30, "Groceries"),           # weekend
    _t(6, "2026-06-06", 20, "Groceries"),            # weekend refund -> nets Groceries
    _t(7, "2026-06-15", 3000, "Salary", source="bank", person_id=2),  # income
    _t(8, "2026-06-03", -40, "Groceries", person_id=2),
    _t(9, "2026-06-04", -500, "Transit", included=0),  # excluded transfer
]


def _weekend_ids(txns):
    return {t["id"] for t in txns
            if date.fromisoformat(t["date"]).weekday() >= 5}


# ---- filter_transactions --------------------------------------------------

def test_filter_excludes_non_included():
    ids = {t["id"] for t in analytics.filter_transactions(TXNS)}
    assert 9 not in ids  # excluded transfer never appears


def test_filter_weekend_vs_weekday():
    wk = analytics.filter_transactions(TXNS, day_types=["weekend"])
    got = {t["id"] for t in wk}
    expected = _weekend_ids(TXNS) - {9}  # 9 is excluded
    assert got == expected
    wd = analytics.filter_transactions(TXNS, day_types=["weekday"])
    assert _weekend_ids(TXNS).isdisjoint({t["id"] for t in wd})


def test_filter_dow_and_daterange_and_category():
    only_groc = analytics.filter_transactions(TXNS, categories=["Groceries"])
    assert all(t["category"] == "Groceries" for t in only_groc)
    rng = analytics.filter_transactions(TXNS, date_range=("2026-06-05", "2026-06-07"))
    assert {t["id"] for t in rng} == {3, 4, 5, 6}


def test_filter_months():
    txns = [
        {"id": 1, "date": "2026-05-10", "amount": -10, "category": "X",
         "source": "credit_card", "included": 1, "description": "a"},
        {"id": 2, "date": "2026-06-10", "amount": -20, "category": "X",
         "source": "credit_card", "included": 1, "description": "b"},
        {"id": 3, "date": "2026-07-10", "amount": -30, "category": "X",
         "source": "credit_card", "included": 1, "description": "c"},
    ]
    got = {t["id"] for t in
           analytics.filter_transactions(txns, months=["2026-05", "2026-07"])}
    assert got == {1, 3}   # non-contiguous month selection


def test_filter_people():
    p2 = analytics.filter_transactions(TXNS, people=[2])
    assert {t["id"] for t in p2} == {7, 8}


def test_filter_event_window_and_recurring():
    win = {"kind": "window", "start_date": "2026-06-05", "end_date": "2026-06-06"}
    assert {t["id"] for t in analytics.filter_transactions(TXNS, event=win)} == {3, 4, 6}
    we = analytics.filter_transactions(TXNS, event=analytics.WEEKENDS)
    assert {t["id"] for t in we} == _weekend_ids(TXNS) - {9}


# ---- day counting / normalization ----------------------------------------

def test_count_matching_days_full_week_invariant():
    # any 7 consecutive days = exactly 2 weekend + 5 weekday days
    assert analytics.count_matching_days("2026-06-01", "2026-06-07",
                                         day_types=["weekend"]) == 2
    assert analytics.count_matching_days("2026-06-01", "2026-06-07",
                                         day_types=["weekday"]) == 5


def test_count_matching_days_window_overlap():
    win = {"kind": "window", "start_date": "2026-06-03", "end_date": "2026-06-05"}
    assert analytics.count_matching_days("2026-06-01", "2026-06-10", event=win) == 3


def test_per_day_normalize():
    sub = analytics.filter_transactions(TXNS, categories=["Eating Out"])
    norm = analytics.per_day_normalize(sub, "2026-06-01", "2026-06-10")  # 10 days
    assert norm["days"] == 10
    assert round(norm["spend"], 2) == 130.0          # 50 + 80
    assert round(norm["spend_per_day"], 2) == 13.0


# ---- compare --------------------------------------------------------------

def test_compare_weekday_vs_weekend_per_day():
    df = analytics.compare(
        TXNS,
        {"label": "Weekdays", "day_types": ["weekday"]},
        {"label": "Weekends", "day_types": ["weekend"]},
    )
    assert set(df["bucket"]) == {"Weekdays", "Weekends"}
    assert (df["per_day"] >= 0).all()


# ---- drill-down -----------------------------------------------------------

def test_drill_levels():
    cats = analytics.drill(TXNS, "category")
    assert round(cats["Groceries"], 2) == 150.0       # 100+30+40-20 refund
    merch = analytics.drill(TXNS, "merchant", parent="Eating Out")
    assert merch  # at least one merchant key
    rows = analytics.drill(
        [t for t in TXNS if t["category"] == "Eating Out"],
        "rows", parent=analytics.keyword_from_desc("Eating Out 3"))
    assert all(t["category"] == "Eating Out" for t in rows)


# ---- people ---------------------------------------------------------------

def test_user_overlap_shared():
    rows = analytics.user_overlap(TXNS, 1, 2)
    groc = next(r for r in rows if r["category"] == "Groceries")
    assert groc["shared"] is True            # both people spent on Groceries
    assert round(groc["a_spend"], 2) == 110.0
    assert round(groc["b_spend"], 2) == 40.0


# ---- budgets + parent rollup ---------------------------------------------

def test_spend_by_parent():
    parents = {"Groceries": "Food", "Eating Out": "Food", "Transit": "Transport"}
    rolled = analytics.spend_by_parent(TXNS, parents)
    assert round(rolled["Food"], 2) == 280.0          # 150 groceries + 130 eating out
    assert round(rolled["Transport"], 2) == 20.0


def test_vendor_grouping_drill():
    rules = [("Amazon", ["amazon", "amzn"]), ("MTA", ["mta", "nyct"])]
    txns = [
        {"id": 1, "date": "2026-06-01", "amount": -10, "category": "Shopping",
         "source": "credit_card", "included": 1,
         "description": "AMAZON MKTPL*AB1 Amzn.com/billWA"},
        {"id": 2, "date": "2026-06-02", "amount": -20, "category": "Shopping",
         "source": "credit_card", "included": 1,
         "description": "Amazon.com*CD2 Amzn.com/billWA"},
        {"id": 3, "date": "2026-06-03", "amount": -5, "category": "Transit",
         "source": "credit_card", "included": 1,
         "description": "MTA*NYCT PAYGO NEW YORK NY"},
    ]
    assert analytics.vendor_of(txns[0]["description"], rules) == "Amazon"
    assert analytics.vendor_of(txns[1]["description"], rules) == "Amazon"
    # Both Amazon variants collapse into one drill bucket.
    v = analytics.drill(txns, "vendor", parent="Shopping", vendor_rules=rules)
    assert list(v.keys()) == ["Amazon"]
    assert round(v["Amazon"], 2) == 30.0
    # Rows for the Amazon vendor return both underlying transactions.
    shopping = [t for t in txns if t["category"] == "Shopping"]
    rows = analytics.drill(shopping, "rows", parent="Amazon", vendor_rules=rules)
    assert {r["id"] for r in rows} == {1, 2}
    # With no rules, it falls back to the auto merchant key (variants may split).
    v2 = analytics.drill(txns, "vendor", parent="Shopping")
    assert len(v2) >= 1


def test_month_end_balances():
    rows = [
        {"id": 1, "date": "2026-04-20", "balance": 500.0},
        {"id": 2, "date": "2026-04-29", "balance": 300.0},   # later April -> month end
        {"id": 3, "date": "2026-05-02", "balance": 800.0},
        {"id": 4, "date": "2026-05-19", "balance": 750.0},   # later May -> month end
        {"id": 5, "date": "2026-05-19", "balance": 700.0},   # same day, higher id wins
        {"id": 6, "date": "2026-05-10", "balance": 999.0, "balance": None},  # no balance
        {"id": 7, "date": "2026-06-01"},                     # missing balance key
    ]
    meb = analytics.month_end_balances(rows)
    assert [m["month"] for m in meb] == ["2026-04", "2026-05"]
    assert meb[0]["balance"] == 300.0
    assert meb[1]["balance"] == 700.0      # id 5 beats id 4 on the same date


def test_budget_status_pacing():
    parents = {"Groceries": "Food", "Eating Out": "Food"}
    budgets = [{"category": "Food", "amount": 400}, {"category": "Transit", "amount": 10}]
    res = {b["category"]: b for b in
           analytics.budget_status(TXNS, budgets, parents=parents, as_of=date(2026, 6, 15))}
    food = res["Food"]
    assert round(food["spent"], 2) == 280.0           # parent rollup (150+130)
    assert food["status"] == "ahead"                  # 280 > pace 200, < cap 400
    transit = res["Transit"]
    assert round(transit["spent"], 2) == 20.0
    assert transit["status"] == "over"                # 20 spent > 10 cap
