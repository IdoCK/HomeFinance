"""CSV / statement format registry, stored in a human-editable Markdown file.

Why this exists: a small local LLM is unreliable at re-deriving a file's layout
on every upload (it flip-flops on which column is the amount and on the sign
convention). Instead we keep a registry of KNOWN layouts in `csv_formats.md`.
On upload we recognize the file's format from that registry and parse it
deterministically with the stored rules — same result every time. The LLM is
only used to *propose* rules for a brand-new format, which you then review and
save back into the registry.

Registry file shape — one `## Identifier` section per format, each followed by a
fenced ```json block with two keys:

  match  — how to RECOGNIZE the file
    header_signature : column-header names that must ALL appear together in one
                       row (case-insensitive). That row is treated as the header.
    file_contains    : optional substrings that must appear somewhere in the file
                       (disambiguates layouts that share the same headers).
  parse  — how to READ it. Column roles are given BY HEADER NAME (looked up in
           the detected header row), so they survive preamble padding and shifts.
    date_header, desc_header, amount_header, debit_header, credit_header
    spend_is_negative     : when the amount column is NOT already signed, is
                            money-out negative?
    amount_already_signed : documentation flag; the parser also auto-detects it
    date_format           : strptime string, or null
    skip_summary_rows     : drop aggregate rows (Total credits / Ending balance …)

The best-scoring format wins (more signature tokens + file_contains = more
specific). Unmatched files raise a warning so a new format can be added.
"""

import os
import re
import json

import pandas as pd

from . import agent_parser

_BLOCK = re.compile(r"^##[ \t]+([^\n]+?)[ \t]*\n+```json\n(.*?)\n```", re.M | re.S)


def default_md_path():
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)), "csv_formats.md"
    )


# ------------------------------------------------------------------ load / save

def load_formats(md_path=None):
    """Parse the registry file into a list of format dicts (each has an
    'identifier' key plus 'match'/'parse'/'source')."""
    md_path = md_path or default_md_path()
    try:
        with open(md_path, encoding="utf-8") as fh:
            text = fh.read()
    except FileNotFoundError:
        return []
    out = []
    for m in _BLOCK.finditer(text):
        try:
            spec = json.loads(m.group(2))
        except json.JSONDecodeError:
            continue
        spec["identifier"] = m.group(1).strip()
        out.append(spec)
    return out


def _format_block(spec):
    body = {k: spec[k] for k in ("source", "match", "parse") if k in spec}
    return f"## {spec['identifier']}\n\n```json\n{json.dumps(body, indent=2)}\n```\n"


def add_format(spec, md_path=None):
    """Append a new format section to the registry (creating the file if needed)."""
    md_path = md_path or default_md_path()
    try:
        with open(md_path, encoding="utf-8") as fh:
            text = fh.read()
    except FileNotFoundError:
        text = "# CSV Format Registry\n"
    if not text.endswith("\n"):
        text += "\n"
    text += "\n" + _format_block(spec)
    with open(md_path, "w", encoding="utf-8") as fh:
        fh.write(text)


# ------------------------------------------------------------------ matching

def _norm(v):
    return ("" if v is None or (isinstance(v, float) and pd.isna(v)) else str(v)).strip().lower()


def find_header_row(raw_df, signature):
    """Return (row_index, [normalized cells]) of the first row that contains
    every header-signature token, else (None, None)."""
    sig = [_norm(s) for s in signature if _norm(s)]
    if not sig:
        return None, None
    for i in range(len(raw_df)):
        cells = [_norm(v) for v in raw_df.iloc[i].tolist()]
        present = {c for c in cells if c}
        if all(tok in present for tok in sig):
            return i, cells
    return None, None


def _col_of(header_cells, name):
    if not name:
        return None
    n = _norm(name)
    for idx, c in enumerate(header_cells):
        if c == n:
            return idx
    return None


def match_format(raw_df, file_text, formats):
    """Pick the best-scoring format whose match rules fit the file.

    Returns (format_dict, header_row_index) or (None, None)."""
    best, best_score, best_row = None, -1, None
    low_text = (file_text or "").lower()
    for fmt in formats:
        match = fmt.get("match", {}) or {}
        sig = match.get("header_signature", []) or []
        row, _cells = find_header_row(raw_df, sig)
        if sig and row is None:
            continue
        contains = match.get("file_contains", []) or []
        if not all(c.lower() in low_text for c in contains):
            continue
        score = len(sig) + len(contains)
        if score > best_score:
            best, best_score, best_row = fmt, score, row
    return best, best_row


# ------------------------------------------------------------------ parse

def parse_with_format(raw_df, fmt, header_row, source, categorize_fn,
                      category_rules, progress_cb=None):
    """Apply a registry format's parse rules deterministically. Returns
    (rows, skipped, statement_balance). statement_balance is the latest-dated
    running balance when the format defines a balance_header, else None.
    progress_cb(done_rows, total_rows) is called periodically."""
    sig = (fmt.get("match", {}) or {}).get("header_signature", [])
    if header_row is None:
        header_row, hdr_cells = find_header_row(raw_df, sig)
    else:
        hdr_cells = [_norm(v) for v in raw_df.iloc[header_row].tolist()]
    if header_row is None:
        return [], 0, None

    p = fmt.get("parse", {}) or {}
    spec = {
        "header_row": header_row,
        "data_starts_row": header_row + 1,
        "date_col": _col_of(hdr_cells, p.get("date_header")),
        "desc_col": _col_of(hdr_cells, p.get("desc_header")),
        "amount_col": _col_of(hdr_cells, p.get("amount_header")),
        "debit_col": _col_of(hdr_cells, p.get("debit_header")),
        "credit_col": _col_of(hdr_cells, p.get("credit_header")),
        "balance_col": _col_of(hdr_cells, p.get("balance_header")),
        "spend_is_negative": p.get("spend_is_negative", True),
        "date_format": p.get("date_format"),
        "exclude_keywords": p.get("exclude_keywords") or [],
    }
    return agent_parser._apply_spec(
        raw_df, spec, source, categorize_fn, category_rules, progress_cb=progress_cb
    )
