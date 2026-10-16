"""Money-math tests for modules.analytics.

These pin down the financial semantics the dashboard and AI insights depend on:
how spend vs income is split, how refunds net against spend, how excluded rows
drop out of every calculation, and how partial statement cycles are flagged.

Run from the repo root:
    venv/Scripts/python.exe -m unittest discover -s tests
"""

import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules import analytics


def tx(date, amount, category="Misc", source="bank", included=1, description="merchant"):
    """Build one transaction dict in the app's common schema."""
    return {
        "date": date,
        "amount": float(amount),
        "category": category,
        "source": source,
        "included": included,
        "description": description,
    }


class SpendIncomeSplit(unittest.TestCase):
    def test_negative_amount_counts_as_spend(self):
        s = analytics.monthly_savings([tx("2025-01-10", -100, source="bank")])
        row = s.iloc[0]
        self.assertEqual(row["spend"], 100)
        self.assertEqual(row["income"], 0)
        self.assertEqual(row["savings"], -100)

    def test_positive_on_bank_counts_as_income(self):
        s = analytics.monthly_savings([tx("2025-01-10", 5000, source="bank")])
        row = s.iloc[0]
        self.assertEqual(row["income"], 5000)
        self.assertEqual(row["spend"], 0)
        self.assertEqual(row["savings"], 5000)


class RefundNetting(unittest.TestCase):
    """A positive amount on a spend feed (credit_card / amazon) is a refund: it
    reduces that category's spend and is never counted as income."""

    def _purchase_and_refund(self, source):
        return [
            tx("2025-01-05", -100, category="Groceries", source=source),
            tx("2025-01-20", 30, category="Groceries", source=source),
        ]

    def test_credit_card_refund_reduces_category_spend(self):
        totals = analytics.category_totals(self._purchase_and_refund("credit_card"))
        self.assertEqual(totals, {"Groceries": 70})

    def test_amazon_refund_reduces_category_spend(self):
        totals = analytics.category_totals(self._purchase_and_refund("amazon"))
        self.assertEqual(totals, {"Groceries": 70})

    def test_refund_is_not_income(self):
        rows = self._purchase_and_refund("credit_card")
        self.assertEqual(analytics.income_by_category(rows), {})
        self.assertEqual(analytics.monthly_savings(rows).iloc[0]["income"], 0)

    def test_savings_equals_net_of_all_amounts(self):
        # Invariant the docstring promises: savings == sum(amount).
        rows = self._purchase_and_refund("credit_card")
        self.assertEqual(analytics.monthly_savings(rows).iloc[0]["savings"], -70)

    def test_fully_refunded_category_drops_out(self):
        rows = [
            tx("2025-01-05", -50, category="Shopping", source="credit_card"),
            tx("2025-01-20", 50, category="Shopping", source="credit_card"),
        ]
        self.assertEqual(analytics.category_totals(rows), {})

    def test_income_by_category_keeps_real_income_excludes_refund(self):
        rows = [
            tx("2025-01-20", 30, category="Groceries", source="credit_card"),  # refund
            tx("2025-01-01", 5000, category="Salary", source="bank"),          # income
        ]
        self.assertEqual(analytics.income_by_category(rows), {"Salary": 5000})


class ExcludedRows(unittest.TestCase):
    """Rows with included=0 (e.g. a credit-card bill payment) drop out of every
    total and chart."""

    def test_excluded_row_dropped_from_savings(self):
        rows = [
            tx("2025-01-01", 5000, category="Salary", source="bank", included=1),
            tx("2025-01-15", -1000, category="Transfer", source="bank", included=0),
        ]
        row = analytics.monthly_savings(rows).iloc[0]
        self.assertEqual(row["income"], 5000)
        self.assertEqual(row["spend"], 0)

    def test_excluded_row_dropped_from_category_totals(self):
        rows = [tx("2025-01-15", -1000, category="Transfer", included=0)]
        self.assertEqual(analytics.category_totals(rows), {})

    def test_included_flag_accepts_bool(self):
        rows = [
            tx("2025-01-01", 100, source="bank", included=True),
            tx("2025-01-02", -40, source="bank", included=False),
        ]
        row = analytics.monthly_savings(rows).iloc[0]
        self.assertEqual(row["income"], 100)
        self.assertEqual(row["spend"], 0)


class SavingsRate(unittest.TestCase):
    def test_rate_is_savings_over_income(self):
        rows = [
            tx("2025-01-01", 1000, source="bank"),
            tx("2025-01-10", -250, source="bank"),
        ]
        self.assertAlmostEqual(analytics.monthly_savings(rows).iloc[0]["savings_rate"], 0.75)

    def test_rate_is_nan_without_income(self):
        rows = [tx("2025-01-10", -100, source="bank")]
        self.assertTrue(math.isnan(analytics.monthly_savings(rows).iloc[0]["savings_rate"]))


class CompleteMonthFlag(unittest.TestCase):
    """A month is 'complete' only when the data spans the whole calendar month."""

    def test_full_coverage_is_complete(self):
        rows = [tx("2025-01-01", -10), tx("2025-01-31", -10)]
        self.assertTrue(bool(analytics.monthly_savings(rows).loc["2025-01", "complete"]))

    def test_single_midmonth_is_not_complete(self):
        rows = [tx("2025-01-15", -10)]
        self.assertFalse(bool(analytics.monthly_savings(rows).loc["2025-01", "complete"]))

    def test_first_and_last_partial_middle_complete(self):
        rows = [tx("2025-01-15", -10), tx("2025-02-15", -10), tx("2025-03-15", -10)]
        s = analytics.monthly_savings(rows)
        self.assertFalse(bool(s.loc["2025-01", "complete"]))  # partial first
        self.assertTrue(bool(s.loc["2025-02", "complete"]))   # fully spanned
        self.assertFalse(bool(s.loc["2025-03", "complete"]))  # partial last


class LatestCompleteMonth(unittest.TestCase):
    def test_returns_most_recent_complete(self):
        rows = [tx("2025-01-15", -10), tx("2025-02-15", -10), tx("2025-03-15", -10)]
        s = analytics.monthly_savings(rows)
        self.assertEqual(analytics.latest_complete_month(s), "2025-02")

    def test_none_when_all_partial(self):
        s = analytics.monthly_savings([tx("2025-01-15", -10)])
        self.assertIsNone(analytics.latest_complete_month(s))

    def test_none_on_empty(self):
        self.assertIsNone(analytics.latest_complete_month(analytics.monthly_savings([])))


class EmptyInputs(unittest.TestCase):
    def test_monthly_savings_empty(self):
        self.assertTrue(analytics.monthly_savings([]).empty)

    def test_category_totals_empty(self):
        self.assertEqual(analytics.category_totals([]), {})

    def test_income_by_category_empty(self):
        self.assertEqual(analytics.income_by_category([]), {})


if __name__ == "__main__":
    unittest.main()
