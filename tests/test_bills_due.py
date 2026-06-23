from modules import analytics


def test_bills_due_counts_charges_due_before_month_end():
    recurring = [
        {"vendor": "Netflix", "next_expected": "2026-05-20", "typical_amount": 15.0},
        {"vendor": "Gym", "next_expected": "2026-05-28", "typical_amount": 40.0},
        {"vendor": "Rent", "next_expected": "2026-06-01", "typical_amount": 2000.0},   # next month
        {"vendor": "Past", "next_expected": "2026-05-01", "typical_amount": 9.0},       # before as_of
    ]
    out = analytics.bills_due_this_month(recurring, as_of="2026-05-15")
    assert out["count"] == 2
    assert out["amount"] == 55.0


def test_bills_due_is_inclusive_of_today_and_month_end():
    recurring = [
        {"vendor": "Today", "next_expected": "2026-05-15", "typical_amount": 10.0},
        {"vendor": "MonthEnd", "next_expected": "2026-05-31", "typical_amount": 20.0},
    ]
    out = analytics.bills_due_this_month(recurring, as_of="2026-05-15")
    assert out["count"] == 2
    assert out["amount"] == 30.0


def test_bills_due_empty():
    assert analytics.bills_due_this_month([], as_of="2026-05-15") == {"count": 0, "amount": 0.0}
