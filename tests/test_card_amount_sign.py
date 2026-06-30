"""Inverted-sign credit-card columns (Israeli cards: positive = money OUT /
spend, negative = money IN / refund). A refund row must not flip the whole
column's interpretation — the format's declared `amount_already_signed: false`
+ `spend_is_negative: false` is authoritative, not the negative-value heuristic.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd

from modules import formats

# A card format using the inverted convention: spend is an unsigned positive
# magnitude, and a leading minus marks money coming back into the account.
CARD_FMT = {
    "source": "credit_card",
    "match": {"header_signature": ["Date", "Business", "Amount to be charged"],
              "file_contains": []},
    "parse": {
        "date_header": "Date",
        "desc_header": "Business",
        "amount_header": "Amount to be charged",
        "debit_header": None,
        "credit_header": None,
        "amount_already_signed": False,
        "spend_is_negative": False,
        "date_format": "%d/%m/%Y",
        "default_currency": "ILS",
    },
}


def _df(rows):
    data = [["Date", "Business", "Amount to be charged"]] + rows
    return pd.DataFrame(data, dtype=object).astype(str)


def _parse(df):
    rows, _skipped, _bal = formats.parse_with_format(
        df, CARD_FMT, 0, "credit_card", lambda d, r: "Uncategorized", [])
    return {r["description"]: r["amount"] for r in rows}


def test_all_spend_no_refund_becomes_negative():
    amts = _parse(_df([
        ["01/03/2026", "Shop A", "100"],
        ["02/03/2026", "Shop B", "50"],
    ]))
    assert amts["Shop A"] == -100  # spend -> money out (negative internally)
    assert amts["Shop B"] == -50


def test_refund_row_does_not_flip_the_column():
    # The single negative refund must NOT make the parser treat the column as
    # standard-signed and leave the positive spends as income.
    amts = _parse(_df([
        ["01/03/2026", "Shop A", "100"],
        ["02/03/2026", "Shop B", "50"],
        ["03/03/2026", "Refund", "-30"],  # money back into the account
    ]))
    assert amts["Shop A"] == -100  # spend stays money OUT
    assert amts["Shop B"] == -50
    assert amts["Refund"] == 30    # refund is money IN (positive internally)
