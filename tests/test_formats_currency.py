import pandas as pd
from modules import agent_parser as ap


def _identity_categorize(desc, rules):
    return "Uncategorized"


def test_explicit_currency_column_wins():
    raw = pd.DataFrame([
        ["Date", "Desc", "Amount", "Ccy"],
        ["2026-03-13", "STORE", "100.00", "ILS"],
    ], dtype=str)
    spec = {"header_row": 0, "data_starts_row": 1, "date_col": 0, "desc_col": 1,
            "amount_col": 2, "currency_col": 3, "file_default": "USD"}
    rows, *_ = ap._apply_spec(raw, spec, "bank", _identity_categorize, [])
    assert rows[0]["currency"] == "ILS"
    assert rows[0]["currency_source"] == "column"


def test_file_default_applies_without_column():
    raw = pd.DataFrame([
        ["Date", "Desc", "Amount"],
        ["2026-03-13", "STORE", "100.00"],
    ], dtype=str)
    spec = {"header_row": 0, "data_starts_row": 1, "date_col": 0, "desc_col": 1,
            "amount_col": 2, "file_default": "ILS"}
    rows, *_ = ap._apply_spec(raw, spec, "bank", _identity_categorize, [])
    assert rows[0]["currency"] == "ILS"
    assert rows[0]["currency_source"] == "file_default"
