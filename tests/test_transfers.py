"""Tests for internal transfer-pair detection (analytics.find_transfer_pairs)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import analytics


def _t(i, d, amount, desc, person_id=1, source="bank", included=1):
    return {"id": i, "date": d, "description": desc, "amount": amount,
            "category": "Uncategorized", "source": source, "person_id": person_id,
            "included": included}


def test_cross_person_transfer_matched():
    txns = [
        _t(1, "2026-05-10", -500, "Zelle payment to Sam", person_id=1),
        _t(2, "2026-05-11", 500, "Zelle payment from Alex", person_id=2),
    ]
    pairs = analytics.find_transfer_pairs(txns)
    assert len(pairs) == 1
    p = pairs[0]
    assert p["amount"] == 500 and p["cross_person"] is True
    assert {p["out_id"], p["in_id"]} == {1, 2}
    assert p["both_included"] is True


def test_same_person_transfer_by_keyword():
    # One person moving money between their own accounts (transfer keyword).
    txns = [
        _t(1, "2026-05-10", -1000, "Online Banking transfer to savings"),
        _t(2, "2026-05-10", 1000, "Online Banking transfer from checking"),
    ]
    pairs = analytics.find_transfer_pairs(txns)
    assert len(pairs) == 1 and pairs[0]["days_apart"] == 0


def test_coincidental_same_amount_not_matched():
    # Same person, same magnitude, no transfer hint -> not a transfer (e.g. a
    # $80 paycheck-adjacent purchase that happens to equal an $80 refund-less buy).
    txns = [
        _t(1, "2026-05-10", -80, "Whole Foods", source="credit_card"),
        _t(2, "2026-05-11", 80, "Acme Payroll", source="bank"),
    ]
    assert analytics.find_transfer_pairs(txns) == []


def test_purchase_and_refund_skipped():
    # Both on a spend feed -> purchase + refund, handled by netting, not a transfer.
    txns = [
        _t(1, "2026-05-10", -60, "Amazon order", source="amazon"),
        _t(2, "2026-05-12", 60, "Amazon refund", source="amazon"),
    ]
    assert analytics.find_transfer_pairs(txns) == []


def test_outside_window_not_matched():
    txns = [
        _t(1, "2026-05-01", -300, "Zelle to Sam", person_id=1),
        _t(2, "2026-05-20", 300, "Zelle from Alex", person_id=2),
    ]
    assert analytics.find_transfer_pairs(txns, days=3) == []


def test_each_row_used_once():
    txns = [
        _t(1, "2026-05-10", -200, "Zelle to Sam", person_id=1),
        _t(2, "2026-05-10", 200, "Zelle from Alex", person_id=2),
        _t(3, "2026-05-10", 200, "Paycheck", person_id=2, source="bank"),
    ]
    pairs = analytics.find_transfer_pairs(txns)
    assert len(pairs) == 1                       # only one outflow, one match
    assert pairs[0]["in_id"] in {2, 3}


def test_reports_already_excluded_pair():
    txns = [
        _t(1, "2026-05-10", -500, "Zelle to Sam", person_id=1, included=0),
        _t(2, "2026-05-11", 500, "Zelle from Alex", person_id=2),
    ]
    pairs = analytics.find_transfer_pairs(txns)
    assert len(pairs) == 1 and pairs[0]["both_included"] is False
