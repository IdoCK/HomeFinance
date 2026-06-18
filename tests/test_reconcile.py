"""Tests for statement reconciliation (analytics.reconcile)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import analytics


def _stmt(opening, txns):
    """Build rows with a correct running balance from an opening balance and a
    list of (date, amount) pairs, in chronological order."""
    rows, bal = [], opening
    for d, amt in txns:
        bal = round(bal + amt, 2)
        rows.append({"date": d, "description": "x", "amount": amt, "balance": bal})
    return rows


def test_clean_statement_reconciles():
    rows = _stmt(1000.0, [("2026-05-01", -50), ("2026-05-03", -20.50),
                          ("2026-05-15", 2000), ("2026-05-20", -130.25)])
    r = analytics.reconcile(rows)
    assert r["ok"] is True
    assert r["begin"] == 1000.0
    assert r["end"] == round(1000 - 50 - 20.50 + 2000 - 130.25, 2)
    assert r["discrepancy"] == 0.0
    assert r["chain_breaks"] == 0
    assert r["n"] == 4


def test_reverse_chronological_still_reconciles():
    rows = _stmt(500.0, [("2026-05-01", -10), ("2026-05-10", -40), ("2026-05-20", 100)])
    rows = list(reversed(rows))               # newest-first export
    r = analytics.reconcile(rows)
    assert r["ok"] is True
    assert r["begin"] == 500.0


def test_discrepancy_detected():
    rows = _stmt(1000.0, [("2026-05-01", -50), ("2026-05-10", -25)])
    rows[-1]["balance"] += 5                   # a balance that doesn't tie out
    r = analytics.reconcile(rows)
    assert r["ok"] is False
    assert r["discrepancy"] == 5.0
    assert r["chain_breaks"] >= 1


def test_no_balance_column_returns_none():
    rows = [{"date": "2026-05-01", "amount": -10, "balance": None},
            {"date": "2026-05-02", "amount": -20, "balance": None}]
    assert analytics.reconcile(rows) is None


def test_single_balance_row_returns_none():
    rows = [{"date": "2026-05-01", "amount": -10, "balance": 990.0}]
    assert analytics.reconcile(rows) is None


def test_mixed_feed_ignores_balanceless_rows():
    # A bank chain that ties, plus credit-card rows with no balance interleaved.
    rows = _stmt(200.0, [("2026-05-01", -10), ("2026-05-05", -5)])
    rows.append({"date": "2026-05-03", "amount": -99, "balance": None})
    r = analytics.reconcile(rows)
    assert r["ok"] is True
    assert r["n"] == 2                          # only balance-bearing rows counted
