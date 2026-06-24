"""Task 1.3 — currency-aware transfer-pair matching.

RED: a ₪370 outflow and a $370 inflow must NOT pair (raw amounts equal, but
     different currencies → not the same money).
GREEN: a $370 outflow and a $370 inflow of the same currency DO pair;
       likewise two legs whose amount_base (USD) values are equal.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from modules import analytics


def _t(i, d, amount, desc, person_id=1, source="bank", included=1,
       currency="USD", amount_base=None):
    """Minimal transaction dict matching the shape analytics.find_transfer_pairs needs."""
    return {
        "id": i,
        "date": d,
        "description": desc,
        "amount": amount,
        "amount_base": amount_base if amount_base is not None else amount,
        "currency": currency,
        "category": "Uncategorized",
        "source": source,
        "person_id": person_id,
        "included": included,
    }


# ---------------------------------------------------------------------------
# Core currency-mismatch guard (RED before fix, GREEN after)
# ---------------------------------------------------------------------------

def test_ils_outflow_usd_inflow_same_raw_do_not_pair():
    """₪370 out vs $370 in — raw amount equals but different currencies.
    These are NOT the same money and must NOT be detected as a transfer pair."""
    txns = [
        # ₪370 outflow: amount_base (USD) ≈ 100 (pretend 1 USD ≈ 3.7 ILS)
        _t(1, "2026-05-10", -370, "Zelle to Sam", person_id=1,
           currency="ILS", amount_base=-100.0),
        # $370 inflow: amount_base = 370
        _t(2, "2026-05-10", 370, "Zelle from Alex", person_id=2,
           currency="USD", amount_base=370.0),
    ]
    pairs = analytics.find_transfer_pairs(txns)
    assert pairs == [], (
        f"Expected no pairs (currency mismatch), got {pairs}"
    )


def test_usd_usd_same_amount_still_pairs():
    """$370 out / $370 in — same currency, same base amount — must still pair."""
    txns = [
        _t(1, "2026-05-10", -370, "Zelle to Sam", person_id=1,
           currency="USD", amount_base=-370.0),
        _t(2, "2026-05-10", 370, "Zelle from Alex", person_id=2,
           currency="USD", amount_base=370.0),
    ]
    pairs = analytics.find_transfer_pairs(txns)
    assert len(pairs) == 1, f"Expected 1 pair for same-currency transfer, got {pairs}"
    assert pairs[0]["amount"] == 370.0


def test_cross_currency_equal_base_pairs():
    """₪370 out / $100 in — different raw amounts, but amount_base equal in USD.
    These represent the same dollars moving across currencies and SHOULD pair."""
    txns = [
        _t(1, "2026-05-10", -370, "Zelle to Sam", person_id=1,
           currency="ILS", amount_base=-100.0),
        _t(2, "2026-05-10", 100, "Zelle from Alex", person_id=2,
           currency="USD", amount_base=100.0),
    ]
    pairs = analytics.find_transfer_pairs(txns)
    assert len(pairs) == 1, (
        f"Expected 1 pair for cross-currency legs with equal USD base, got {pairs}"
    )


def test_ils_ils_same_raw_same_base_pairs():
    """₪370 out / ₪370 in — same currency, same amount — should pair normally."""
    txns = [
        _t(1, "2026-05-10", -370, "Transfer to savings", person_id=1,
           currency="ILS", amount_base=-100.0),
        _t(2, "2026-05-10", 370, "Transfer from checking", person_id=1,
           currency="ILS", amount_base=100.0),
    ]
    pairs = analytics.find_transfer_pairs(txns)
    assert len(pairs) == 1, f"Expected 1 pair for same ILS transfer, got {pairs}"


def test_currency_fields_surfaced_in_pair():
    """Each pair leg should carry out_currency and in_currency."""
    txns = [
        _t(1, "2026-05-10", -370, "Zelle to Sam", person_id=1,
           currency="USD", amount_base=-370.0),
        _t(2, "2026-05-10", 370, "Zelle from Alex", person_id=2,
           currency="USD", amount_base=370.0),
    ]
    pairs = analytics.find_transfer_pairs(txns)
    assert len(pairs) == 1
    p = pairs[0]
    assert "out_currency" in p, "pair dict must carry out_currency"
    assert "in_currency" in p, "pair dict must carry in_currency"
    assert p["out_currency"] == "USD"
    assert p["in_currency"] == "USD"
