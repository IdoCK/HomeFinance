"""Tests for recurring / subscription detection. Fixtures are synthetic and
self-describing; expectations derive from the data so they're date-independent."""

import os
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import analytics


def _t(i, d, amount, description, category, source="credit_card",
       person_id=1, included=1):
    return {"id": i, "date": d, "description": description, "amount": amount,
            "category": category, "source": source, "person_id": person_id,
            "included": included}


def _monthly(start, months, amount, desc, cat, first_id=1):
    """A charge on the same day-of-month for `months` consecutive months."""
    out = []
    y, m, day = start
    for k in range(months):
        mm = m + k
        yy, mm = y + (mm - 1) // 12, (mm - 1) % 12 + 1
        out.append(_t(first_id + k, f"{yy:04d}-{mm:02d}-{day:02d}",
                      -amount, desc, cat))
    return out


def _by_vendor(recurring):
    return {r["vendor"]: r for r in recurring}


# ---- detection ------------------------------------------------------------

def test_clean_monthly_subscription_detected_as_fixed():
    txns = _monthly((2026, 1, 5), 6, 15.99, "Netflix", "Streaming")
    rec = analytics.recurring_charges(txns)
    assert len(rec) == 1
    r = rec[0]
    assert r["cadence"] == "monthly"
    assert r["kind"] == "fixed"
    assert r["count"] == 6
    assert abs(r["typical_amount"] - 15.99) < 0.01
    assert abs(r["monthly_cost"] - 15.99) < 0.05
    assert abs(r["annual_cost"] - 15.99 * 12) < 0.6
    assert r["confidence"] > 0.7


def test_weekly_cadence_and_monthly_normalization():
    base = date(2026, 2, 2)
    txns = [_t(i, (base + timedelta(weeks=i)).isoformat(), -10, "Gym Class",
               "Fitness") for i in range(6)]
    rec = analytics.recurring_charges(txns)
    assert len(rec) == 1
    assert rec[0]["cadence"] == "weekly"
    # ~4.33 weeks per month -> ~$43/mo
    assert 40 < rec[0]["monthly_cost"] < 47


def test_yearly_cadence_normalized_to_monthly():
    txns = [_t(i, f"{2023 + i}-03-10", -120, "Domain Renewal", "Software")
            for i in range(3)]
    rec = analytics.recurring_charges(txns)
    assert len(rec) == 1
    assert rec[0]["cadence"] == "yearly"
    assert abs(rec[0]["monthly_cost"] - 10) < 0.5


def test_variable_bill_detected_as_variable():
    # Regular monthly cadence, swinging amount (a phone/electric bill).
    amts = [80, 110, 65, 130, 95, 120]
    txns = [_t(i, f"2026-0{(i % 6) + 1}-15".replace("06", "06"), -a, "Con Edison",
               "Utilities") for i, a in enumerate(amts)]
    # build proper consecutive months
    txns = [_t(i, f"2026-{i + 1:02d}-15", -a, "Con Edison", "Utilities")
            for i, a in enumerate(amts)]
    rec = analytics.recurring_charges(txns)
    assert len(rec) == 1
    assert rec[0]["cadence"] == "monthly"
    assert rec[0]["kind"] == "variable"


def test_irregular_merchant_not_recurring():
    # Groceries at random intervals, varying amounts -> not a subscription.
    days = ["2026-01-03", "2026-01-19", "2026-02-21", "2026-02-22", "2026-04-10"]
    amts = [54, 12, 88, 7, 130]
    txns = [_t(i, d, -a, "Whole Foods Market", "Groceries")
            for i, (d, a) in enumerate(zip(days, amts))]
    rec = analytics.recurring_charges(txns)
    assert rec == []


def test_fewer_than_three_charges_not_recurring():
    txns = _monthly((2026, 1, 5), 2, 9.99, "Spotify", "Streaming")
    assert analytics.recurring_charges(txns) == []


def test_excluded_and_refunds_handled():
    txns = _monthly((2026, 1, 5), 4, 20, "Apple iCloud", "Software")
    # An excluded row and a refund for the same vendor must not break/inflate it.
    txns.append(_t(50, "2026-02-10", -20, "Apple iCloud", "Software", included=0))
    txns.append(_t(51, "2026-03-06", 20, "Apple iCloud", "Software"))  # refund
    rec = _by_vendor(analytics.recurring_charges(txns))
    assert "Apple" in rec or any("apple" in v.lower() for v in rec)


def test_vendor_rules_collapse_variants():
    rules = [("Amazon Prime", ["amazon", "amzn"])]
    txns = [
        _t(1, "2026-01-12", -14.99, "AMAZON PRIME*A1", "Subscriptions"),
        _t(2, "2026-02-12", -14.99, "Amazon Prime Membership", "Subscriptions"),
        _t(3, "2026-03-12", -14.99, "AMZN PRIME 888", "Subscriptions"),
    ]
    rec = analytics.recurring_charges(txns, vendor_rules=rules)
    assert len(rec) == 1
    assert rec[0]["vendor"] == "Amazon Prime"
    assert rec[0]["count"] == 3


# ---- committed totals -----------------------------------------------------

def test_committed_monthly_splits_fixed_and_variable():
    netflix = _monthly((2026, 1, 5), 4, 15, "Netflix", "Streaming", first_id=1)
    bill = [_t(20 + i, f"2026-{i + 1:02d}-20", -a, "Con Edison", "Utilities")
            for i, a in enumerate([80, 120, 70, 130])]
    rec = analytics.recurring_charges(netflix + bill)
    tot = analytics.committed_monthly(rec)
    assert abs(tot["fixed"] - 15) < 0.5
    assert tot["variable"] > 0
    assert abs(tot["total"] - (tot["fixed"] + tot["variable"])) < 0.01


# ---- anomalies ------------------------------------------------------------

def test_anomaly_price_change():
    txns = _monthly((2026, 1, 5), 4, 10, "Hulu", "Streaming")
    # Bump the most recent charge: a price hike.
    txns[-1]["amount"] = -15
    rec = analytics.recurring_charges(txns)
    anomalies = analytics.recurring_anomalies(rec, as_of="2026-04-10")
    assert any(a["type"] == "price_change" and a["pct"] > 15 for a in anomalies)


def test_anomaly_possibly_canceled():
    txns = _monthly((2026, 1, 5), 4, 12, "NYTimes", "News")
    # Last charge in April; by August it's long overdue.
    rec = analytics.recurring_charges(txns)
    anomalies = analytics.recurring_anomalies(rec, as_of="2026-08-15")
    assert any(a["type"] == "possibly_canceled" for a in anomalies)


def test_anomaly_new_subscription():
    # First charge two months before as_of -> newly appeared.
    txns = _monthly((2026, 4, 5), 3, 8, "Disney Plus", "Streaming")
    rec = analytics.recurring_charges(txns)
    anomalies = analytics.recurring_anomalies(rec, as_of="2026-06-10")
    assert any(a["type"] == "new" for a in anomalies)


def test_long_running_sub_not_flagged_new():
    txns = _monthly((2024, 1, 5), 18, 9.99, "Spotify", "Streaming")
    rec = analytics.recurring_charges(txns)
    anomalies = analytics.recurring_anomalies(rec, as_of="2025-06-10")
    assert not any(a["type"] == "new" for a in anomalies)
