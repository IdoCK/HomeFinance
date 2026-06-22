"""Net-worth money math for modules.analytics (Wave 2 of the overhaul).

Pins down how assets/liabilities/net are summed and how the trend forward-fills
each account's most-recent snapshot across the dates that have any snapshot.

Run from the repo root:
    venv/Scripts/python.exe -m unittest discover -s tests
"""

import os
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from modules import analytics
from modules import agent_parser
from modules import database as db


def acct(balance, is_asset=1, name="acct"):
    return {"name": name, "is_asset": is_asset, "balance": float(balance)}


def snap(account_id, date, balance, is_asset=1):
    return {"account_id": account_id, "date": date,
            "balance": float(balance), "is_asset": is_asset}


class NetWorth(unittest.TestCase):
    def test_empty_is_all_zero(self):
        self.assertEqual(analytics.net_worth([]),
                         {"assets": 0.0, "liabilities": 0.0, "net": 0.0})

    def test_assets_minus_liabilities(self):
        accounts = [acct(1000, 1), acct(250, 1), acct(400, 0)]
        nw = analytics.net_worth(accounts)
        self.assertEqual(nw["assets"], 1250)
        self.assertEqual(nw["liabilities"], 400)
        self.assertEqual(nw["net"], 850)

    def test_liability_only_is_negative_net(self):
        nw = analytics.net_worth([acct(4200, 0)])
        self.assertEqual(nw, {"assets": 0.0, "liabilities": 4200.0, "net": -4200.0})


class NetWorthTrend(unittest.TestCase):
    def test_empty_is_empty(self):
        self.assertTrue(analytics.net_worth_trend([]).empty)

    def test_single_account_single_date(self):
        df = analytics.net_worth_trend([snap(1, "2025-01-01", 100, is_asset=1)])
        self.assertEqual(len(df), 1)
        row = df.iloc[0]
        self.assertEqual(row["assets"], 100)
        self.assertEqual(row["liabilities"], 0)
        self.assertEqual(row["net"], 100)

    def test_forward_fill_across_dates(self):
        # acct1 (asset): 100 on Jan, rises to 150 on Mar.
        # acct2 (liability): 40 on Feb (didn't exist in Jan).
        snaps = [
            snap(1, "2025-01-01", 100, is_asset=1),
            snap(1, "2025-03-01", 150, is_asset=1),
            snap(2, "2025-02-01", 40, is_asset=0),
        ]
        df = analytics.net_worth_trend(snaps).set_index("date")
        # Jan: acct1=100, acct2 doesn't exist yet -> 0
        self.assertEqual(df.loc["2025-01-01", "net"], 100)
        # Feb: acct1 forward-filled at 100, acct2 liability 40 -> 60
        self.assertEqual(df.loc["2025-02-01", "assets"], 100)
        self.assertEqual(df.loc["2025-02-01", "liabilities"], 40)
        self.assertEqual(df.loc["2025-02-01", "net"], 60)
        # Mar: acct1 rises to 150, acct2 still 40 -> 110
        self.assertEqual(df.loc["2025-03-01", "assets"], 150)
        self.assertEqual(df.loc["2025-03-01", "net"], 110)

    def test_one_snapshot_per_account_uses_latest_on_or_before(self):
        # Two snapshots for the same account before a later date: the latest wins.
        snaps = [
            snap(1, "2025-01-01", 100, is_asset=1),
            snap(1, "2025-01-15", 120, is_asset=1),
        ]
        df = analytics.net_worth_trend(snaps).set_index("date")
        self.assertEqual(df.loc["2025-01-15", "assets"], 120)


class AccountsDB(unittest.TestCase):
    """Integration smoke against a throwaway DB (mirrors the existing DB style)."""

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self._orig = db.DB_PATH
        db.DB_PATH = Path(self.tmp) / "test.db"
        db.init_db()  # seeds people Ido=1, Aviv=2

    def tearDown(self):
        db.DB_PATH = self._orig
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_add_and_list_account(self):
        db.add_account(1, "BofA Checking", "checking", 1, 1000.0)
        accts = db.list_accounts(1)
        self.assertEqual(len(accts), 1)
        self.assertEqual(accts[0]["name"], "BofA Checking")
        self.assertEqual(accts[0]["balance"], 1000.0)

    def test_per_view_filtering(self):
        db.add_account(1, "A1", "checking", 1, 100)
        db.add_account(2, "A2", "checking", 1, 200)
        db.add_account(None, "Shared", "savings", 1, 300)
        self.assertEqual(len(db.list_accounts(1)), 1)      # person 1 only
        self.assertEqual(len(db.list_accounts(None)), 1)   # shared only
        self.assertEqual(len(db.list_accounts("all")), 3)  # household = everything

    def test_update_balance_writes_snapshot(self):
        aid = db.add_account(1, "A", "checking", 1, 100)
        db.update_account_balance(aid, 150, snapshot_date="2025-02-01")
        self.assertEqual(db.list_accounts(1)[0]["balance"], 150)
        dates = {s["date"] for s in db.get_snapshots("all")
                 if s["account_id"] == aid}
        self.assertIn("2025-02-01", dates)

    def test_snapshot_upsert_one_per_day(self):
        aid = db.add_account(1, "A", "checking", 1, 100)
        db.write_snapshot(aid, "2025-03-01", 500)
        db.write_snapshot(aid, "2025-03-01", 700)  # same day overwrites
        same_day = [s for s in db.get_snapshots("all")
                    if s["account_id"] == aid and s["date"] == "2025-03-01"]
        self.assertEqual(len(same_day), 1)
        self.assertEqual(same_day[0]["balance"], 700)

    def test_delete_cascades_snapshots(self):
        aid = db.add_account(1, "A", "checking", 1, 100)
        db.write_snapshot(aid, "2025-03-01", 500)
        db.delete_account(aid)
        self.assertEqual(db.list_accounts(1), [])
        self.assertEqual([s for s in db.get_snapshots("all")
                          if s["account_id"] == aid], [])

    def test_snapshots_carry_is_asset_for_trend(self):
        aid = db.add_account(1, "Loan", "loan", 0, 4200)
        snaps = [s for s in db.get_snapshots("all") if s["account_id"] == aid]
        self.assertTrue(snaps and all(s["is_asset"] == 0 for s in snaps))


class StatementBalanceCapture(unittest.TestCase):
    """_apply_spec returns the latest-dated running balance when balance_col is
    set — the seed for auto-refreshing an account from a bank statement."""

    def _raw(self):
        return pd.DataFrame([
            ["Date", "Description", "Amount", "Running Bal."],
            ["01/01/2025", "Coffee", "-5.00", "1,000.00"],
            ["01/03/2025", "Paycheck", "2000.00", "$3,000.00"],
            ["01/02/2025", "Snack", "-3.00", "997.00"],
        ], dtype=str)

    def _spec(self, balance_col):
        return {"header_row": 0, "data_starts_row": 1, "date_col": 0,
                "desc_col": 1, "amount_col": 2, "balance_col": balance_col,
                "spend_is_negative": True, "date_format": None}

    def test_picks_latest_dated_balance(self):
        rows, skipped, bal = agent_parser._apply_spec(
            self._raw(), self._spec(3), "bank", lambda d, r: "Misc", [])
        self.assertEqual(len(rows), 3)
        self.assertEqual(bal, {"amount": 3000.0, "date": "2025-01-03"})

    def test_none_when_no_balance_col(self):
        rows, skipped, bal = agent_parser._apply_spec(
            self._raw(), self._spec(None), "bank", lambda d, r: "Misc", [])
        self.assertIsNone(bal)


if __name__ == "__main__":
    unittest.main()
