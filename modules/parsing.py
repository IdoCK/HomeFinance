"""Parse uploaded CSV / spreadsheet files into a common transaction schema.

Common schema (one dict per row):
    date         ISO 'YYYY-MM-DD'
    description  free text (merchant / item)
    amount       float, negative = spend, positive = income
    category     auto-assigned from the person's category keyword rules
    source       'amazon' | 'credit_card' | 'bank' | 'generic'

The parser is forgiving: it sniffs likely column names rather than requiring an
exact format, because every bank/card exports differently. Anything it can't map
is left for the user to review.
"""

import io
import pandas as pd

# Candidate column names we look for, in priority order.
DATE_COLS = ["date", "transaction date", "order date", "posted date", "trans date"]
DESC_COLS = ["description", "title", "name", "merchant", "details", "memo", "item"]
AMOUNT_COLS = ["amount", "total", "item total", "debit", "value", "transaction amount"]


def _read_any(file_bytes, filename):
    """Read CSV or Excel bytes into a DataFrame."""
    name = filename.lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(file_bytes))
    return pd.read_csv(io.BytesIO(file_bytes))


def _find_col(df_cols, candidates):
    lower = {c.lower().strip(): c for c in df_cols}
    for cand in candidates:
        if cand in lower:
            return lower[cand]
    # fuzzy: any column that contains the candidate word
    for cand in candidates:
        for lc, original in lower.items():
            if cand in lc:
                return original
    return None


def categorize(description, category_rules):
    """category_rules: list of (name, [keywords]). First keyword match wins."""
    text = (description or "").lower()
    for name, keywords in category_rules:
        for kw in keywords:
            if kw and kw.lower().strip() in text:
                return name
    return "Uncategorized"


def parse_file(file_bytes, filename, source, category_rules):
    """Return (rows, warnings)."""
    warnings = []
    df = _read_any(file_bytes, filename)
    df.columns = [str(c) for c in df.columns]

    date_col = _find_col(df.columns, DATE_COLS)
    desc_col = _find_col(df.columns, DESC_COLS)
    amt_col = _find_col(df.columns, AMOUNT_COLS)

    if not (date_col and amt_col):
        raise ValueError(
            f"Could not find date and amount columns in {filename}. "
            f"Found columns: {list(df.columns)}"
        )
    if not desc_col:
        warnings.append(f"No description column in {filename}; using blank descriptions.")

    rows = []
    for _, r in df.iterrows():
        # date
        try:
            date = pd.to_datetime(r[date_col]).date().isoformat()
        except Exception:
            continue  # skip rows with unparseable dates

        # amount: strip currency symbols/commas, handle parentheses as negative
        raw = str(r[amt_col]).replace("$", "").replace(",", "").strip()
        neg = raw.startswith("(") and raw.endswith(")")
        raw = raw.strip("()")
        try:
            amount = float(raw)
        except ValueError:
            continue
        if neg:
            amount = -amount
        # Amazon item-total exports are positive but represent spending.
        if source in ("amazon", "credit_card") and amount > 0:
            amount = -amount

        desc = str(r[desc_col]) if desc_col else ""
        rows.append(
            {
                "date": date,
                "description": desc,
                "amount": amount,
                "category": categorize(desc, category_rules),
                "source": source,
            }
        )

    if not rows:
        warnings.append(f"No usable rows parsed from {filename}.")
    return rows, warnings
