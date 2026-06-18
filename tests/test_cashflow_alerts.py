"""Tests for the cash-flow chart series and rolling-baseline spending alerts."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import analytics


def _t(d, amount, category, source="credit_card"):
    return {"date": d, "description": category, "amount": amount,
            "category": category, "source": source, "included": 1}


def _full_month(ym, rows):
    """Pad a month with boundary rows so monthly_savings marks it complete
    (data must span the 1st..last day)."""
    import calendar
    y, m = int(ym[:4]), int(ym[5:7])
    last = calendar.monthrange(y, m)[1]
    return ([_t(f"{ym}-01", 0, "Pad", source="bank"),
             _t(f"{ym}-{last:02d}", 0, "Pad", source="bank")] + rows)


# ---- cash_flow ------------------------------------------------------------

def test_cash_flow_net_and_cumulative():
    txns = (_full_month("2026-01", [_t("2026-01-10", 3000, "Salary", "bank"),
                                    _t("2026-01-15", -1000, "Rent")])
            + _full_month("2026-02", [_t("2026-02-10", 3000, "Salary", "bank"),
                                      _t("2026-02-15", -2000, "Rent")]))
    cf = analytics.cash_flow(txns)
    assert list(cf["month"]) == ["2026-01", "2026-02"]
    jan, feb = cf.iloc[0], cf.iloc[1]
    assert jan["net"] == 2000      # 3000 - 1000
    assert feb["net"] == 1000      # 3000 - 2000
    assert jan["cumulative"] == 2000
    assert feb["cumulative"] == 3000


def test_cash_flow_empty():
    assert analytics.cash_flow([]).empty


# ---- spending_alerts ------------------------------------------------------

def _baseline_plus_current(cat_baseline, cat_current):
    txns = []
    for ym in ("2026-01", "2026-02", "2026-03"):
        txns += _full_month(ym, [_t(f"{ym}-12", -cat_baseline, "Eating Out")])
    txns += _full_month("2026-04", [_t("2026-04-12", -cat_current, "Eating Out")])
    return txns


def test_alert_on_spike():
    # Baseline ~$200/mo, current $500 -> +150%, flagged up.
    a = analytics.spending_alerts(_baseline_plus_current(200, 500))
    eat = [x for x in a if x["category"] == "Eating Out"]
    assert eat and eat[0]["direction"] == "up"
    assert eat[0]["pct"] > 40
    assert eat[0]["baseline"] == 200


def test_alert_on_drop():
    a = analytics.spending_alerts(_baseline_plus_current(400, 100))
    eat = [x for x in a if x["category"] == "Eating Out"]
    assert eat and eat[0]["direction"] == "down"


def test_no_alert_when_steady():
    a = analytics.spending_alerts(_baseline_plus_current(300, 310))
    assert not [x for x in a if x["category"] == "Eating Out"]


def test_new_category_flagged():
    txns = []
    for ym in ("2026-01", "2026-02", "2026-03"):
        txns += _full_month(ym, [_t(f"{ym}-12", -300, "Groceries")])
    # A brand-new category appears only in the current month.
    txns += _full_month("2026-04", [_t("2026-04-12", -300, "Groceries"),
                                    _t("2026-04-20", -250, "Boat")])
    a = analytics.spending_alerts(txns)
    boat = [x for x in a if x["category"] == "Boat"]
    assert boat and boat[0]["new"] is True and boat[0]["baseline"] == 0.0


def test_partial_current_month_excluded():
    # Three complete months + a partial April (no boundary pad) -> April ignored,
    # so no spurious "spending dropped" alert from the half-month.
    txns = []
    for ym in ("2026-01", "2026-02", "2026-03"):
        txns += _full_month(ym, [_t(f"{ym}-12", -300, "Eating Out")])
    txns += [_t("2026-04-05", -20, "Eating Out")]      # partial, not padded
    a = analytics.spending_alerts(txns)
    assert not [x for x in a if x["category"] == "Eating Out"]


def test_too_few_months():
    txns = _full_month("2026-03", [_t("2026-03-12", -300, "Eating Out")])
    assert analytics.spending_alerts(txns) == []
