"""Local, web-free file-parsing agent backed by Ollama (default model: qwen2.5).

Why an agent and not just code: every bank/card/Amazon export uses a different
layout — different column names, separate debit/credit columns, junk preamble
rows, varied date formats and sign conventions. Instead of hand-coding rules for
each, the agent shows a small sample of the file to a LOCAL LLM and asks it to
return a structured "format spec" (which columns mean what, how signs work,
how many junk rows to skip). The spec is then applied deterministically with
pandas to every row — fast, and the model only ever sees a few sample rows.

Privacy: the model runs entirely on your machine via Ollama (localhost:11434).
Nothing is sent to the web. There is no fallback to any cloud API in this module.

Setup:
    1. Install Ollama:        https://ollama.com
    2. Pull the model:        ollama pull qwen2.5
    3. Ollama serves at       http://localhost:11434  (no internet needed after pull)
"""

import io
import json
import time
import socket
import urllib.request
import urllib.error

import pandas as pd

OLLAMA_URL = "http://localhost:11434/api/chat"
DEFAULT_MODEL = "qwen2.5"
# Descriptions per categorization request. Kept small so each call finishes well
# under the per-request timeout even on slower (CPU-only) machines.
CATEGORIZE_BATCH = 8


def _post_chat_json(payload, timeout=120, attempts=3):
    """POST a chat request to Ollama and return the parsed JSON content.

    Retries on connection/timeout errors with a short backoff — the first call
    often pays a cold model-load cost, so a retry usually hits a warm model and
    succeeds. Raises RuntimeError with the last error if all attempts fail.
    """
    payload = {"keep_alive": "10m", **payload}  # keep the model warm between calls
    data = json.dumps(payload).encode()
    last_err = None
    for i in range(attempts):
        try:
            req = urllib.request.Request(
                OLLAMA_URL, data=data,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = json.loads(resp.read().decode())
            return json.loads(body["message"]["content"])
        except (urllib.error.URLError, socket.timeout, TimeoutError, OSError) as e:
            last_err = getattr(e, "reason", e) or e
            if i < attempts - 1:
                time.sleep(min(2 * (i + 1), 5))  # 2s, 4s backoff
    raise RuntimeError(
        f"Ollama request failed after {attempts} attempt(s) "
        f"(timeout={timeout}s each): {last_err}. Is Ollama running and the "
        f"model pulled? Try again — the model may still be loading."
    )


# --------------------------------------------------------------------------- IO

def _read_raw_table(file_bytes, filename):
    """Read a file into a DataFrame WITHOUT assuming the header position.

    We read with header=None so the agent can decide which row is the real header
    and how many preamble/junk rows to skip.
    """
    name = filename.lower()
    if name.endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(file_bytes), header=None, dtype=str)
    # CSV/TSV: bank exports often have junk preamble lines with a different
    # field count than the data, which trips pandas' column inference. So we
    # detect the separator by scanning raw lines, then split manually and pad
    # every row to the widest width.
    text = file_bytes.decode("utf-8-sig", errors="replace")
    lines = [ln for ln in text.splitlines() if ln.strip() != ""]
    if not lines:
        return pd.DataFrame()

    import csv as _csv
    # Pick the separator that yields the most columns on the most common line.
    best_sep, best_width = ",", 0
    for sep in (",", "\t", ";", "|"):
        widths = {}
        for ln in lines[:30]:
            n = len(next(_csv.reader([ln], delimiter=sep)))
            widths[n] = widths.get(n, 0) + 1
        # most frequent width for this sep
        mode_width = max(widths, key=widths.get) if widths else 1
        if mode_width > best_width:
            best_width, best_sep = mode_width, sep

    parsed = list(_csv.reader(lines, delimiter=best_sep))
    width = max(len(row) for row in parsed)
    padded = [row + [""] * (width - len(row)) for row in parsed]
    return pd.DataFrame(padded, dtype=str)


def _sample_text(raw_df, n=8):
    """A compact, line-numbered preview of the first n rows for the prompt."""
    lines = []
    for i in range(min(n, len(raw_df))):
        cells = [("" if pd.isna(v) else str(v)) for v in raw_df.iloc[i].tolist()]
        lines.append(f"row {i}: " + " | ".join(cells))
    return "\n".join(lines)


# ------------------------------------------------------------------- the agent

SYSTEM = (
    "You are a data-parsing agent. You are given the first rows of a raw "
    "financial export (bank, credit card, or Amazon). Identify the structure and "
    "respond with ONLY a JSON object — no prose, no markdown fences.\n\n"
    "IMPORTANT — summary blocks: many exports begin with a SUMMARY/preamble "
    "section (rows such as 'Beginning balance', 'Total credits', 'Total debits', "
    "'Ending balance') BEFORE the real per-transaction table. IGNORE that summary "
    "section. Point header_row and data_starts_row at the REAL transaction table "
    "— the one whose header has a Date column with many dated rows beneath it.\n\n"
    "JSON fields:\n"
    "  header_row:        integer index of the row containing column headers\n"
    "  data_starts_row:   integer index of the first real data row\n"
    "  date_col:          integer column index for the transaction date\n"
    "  desc_col:          integer column index for the description/merchant\n"
    "  amount_col:        integer column index for a SINGLE column that holds one "
    "number per transaction (e.g. a column titled 'Amount'), or null\n"
    "  debit_col:         integer column index for debits, or null\n"
    "  credit_col:        integer column index for credits, or null\n"
    "  spend_is_negative: boolean — in amount_col, is money-out negative?\n"
    "  date_format:       a Python strptime format string if obvious, else null\n\n"
    "Choosing amount_col vs debit_col/credit_col:\n"
    "  - If there is ONE number column (even when some of its values are "
    "negative), use amount_col and set debit_col=credit_col=null. A column "
    "titled 'Amount' where money-out is negative and money-in is positive is an "
    "amount_col with spend_is_negative=true. Do NOT call it a debit column.\n"
    "  - Use debit_col/credit_col ONLY when the file has TWO SEPARATE number "
    "columns, one for money out and one for money in.\n"
    "Ignore any running-balance column. Columns are 0-indexed."
)


def _call_ollama(model, sample, filename):
    payload = {
        "model": model,
        "format": "json",          # ask Ollama to constrain output to JSON
        "stream": False,
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": SYSTEM},
            {
                "role": "user",
                "content": f"Filename: {filename}\nFirst rows:\n{sample}\n\nReturn the JSON spec.",
            },
        ],
    }
    return _post_chat_json(payload, timeout=120, attempts=3)


# --------------------------------------------------------------- apply the spec

# Currency signals read from the RAW cell BEFORE _clean_amount strips symbols.
_SYMBOL_CCY = {"₪": "ILS", "$": "USD", "€": "EUR", "£": "GBP"}
_CODE_CCY = {"ILS": "ILS", "NIS": "ILS", "SHEKEL": "ILS", "SHEKELS": "ILS",
             "USD": "USD", "US$": "USD", "EUR": "EUR", "GBP": "GBP"}


def _detect_currency(amount_cell, desc_cell, file_default):
    """Return (iso_code, source). Precedence: cell symbol/ISO code, then the
    per-file default, then the person default ('USD' for this household)."""
    blob = f"{amount_cell or ''} {desc_cell or ''}"
    up = blob.upper()
    for code in _CODE_CCY:                      # ISO codes first (most explicit)
        if code in up:
            return _CODE_CCY[code], "cell_code"
    for sym, code in _SYMBOL_CCY.items():
        if sym in blob:
            return code, "cell_symbol"
    if file_default:
        return file_default, "file_default"
    return "USD", "person_default"


def _clean_amount(raw):
    if raw is None:
        return None
    s = str(raw).replace("$", "").replace(",", "").strip()
    if s == "" or s.lower() == "nan":
        return None
    neg = s.startswith("(") and s.endswith(")")
    s = s.strip("()").replace("−", "-")  # normalize unicode minus
    try:
        val = float(s)
    except ValueError:
        return None
    return -val if neg else val


# Description fragments that mark a summary/aggregate row, never a transaction.
_SUMMARY_DESC = (
    "beginning balance", "ending balance", "total credits", "total debits",
    "total credit", "total debit",
)


def _is_summary_row(desc):
    d = (desc or "").lower().strip()
    return any(k in d for k in _SUMMARY_DESC)


def _column_has_negative(raw_df, col, start):
    """True if a column holds any negative value among the data rows.

    A genuine one-sided debit/credit column holds unsigned magnitudes; if the
    column actually contains negatives it is really a single SIGNED amount
    column that the model mislabeled.
    """
    if col is None:
        return False
    for i in range(start, len(raw_df)):
        v = _clean_amount(raw_df.iloc[i][col])
        if v is not None and v < 0:
            return True
    return False


def _apply_spec(raw_df, spec, source, categorize_fn, category_rules,
                progress_cb=None, file_default=None):
    start = int(spec.get("data_starts_row", (spec.get("header_row", 0) + 1)))
    currency_col = spec.get("currency_col")
    file_default = spec.get("file_default", file_default)
    date_col = spec.get("date_col")
    desc_col = spec.get("desc_col")
    amount_col = spec.get("amount_col")
    debit_col = spec.get("debit_col")
    credit_col = spec.get("credit_col")
    balance_col = spec.get("balance_col")  # optional running-balance column
    spend_neg = spec.get("spend_is_negative", True)
    date_fmt = spec.get("date_format")
    # Description fragments for internal transfers (e.g. paying the credit-card
    # bill from checking). These are not spend or income — and importing both a
    # bank and a card statement records the same transfer on each, so counting
    # them would double-count. Dropped like summary rows.
    exclude = [k.lower() for k in (spec.get("exclude_keywords") or []) if k]

    # Repair a common misclassification: the model labels a single SIGNED amount
    # column as debit_col (or credit_col) with the other side null. Forcing such
    # a column to one sign turns every credit into spend (the classic "total
    # credits + total debits = total spent" bug). If exactly one side is given
    # and that column contains negative values, treat it as a signed amount col.
    if amount_col is None and (debit_col is None) != (credit_col is None):
        lone = debit_col if debit_col is not None else credit_col
        if _column_has_negative(raw_df, lone, start):
            amount_col = lone
            debit_col = credit_col = None

    # If the amount column already carries signs (some values negative), those
    # signs ARE the direction — money-out negative, money-in positive. Trust the
    # data over the model's spend_is_negative guess, which qwen gets wrong on
    # signed columns and would otherwise flip every credit into a debit.
    amount_already_signed = (
        amount_col is not None and _column_has_negative(raw_df, amount_col, start)
    )

    rows, skipped = [], 0
    statement_balance = None  # latest-dated running balance, if balance_col is set
    total_rows = max(len(raw_df) - start, 0)
    # Report progress ~every 1% of rows (min 1, max 50) to stay responsive on
    # big files without re-rendering on every single row of small ones.
    update_every = max(1, min(50, total_rows // 100))
    for i in range(start, len(raw_df)):
        if progress_cb and (i - start) % update_every == 0:
            progress_cb(i - start, total_rows)
        r = raw_df.iloc[i]

        # --- skip summary/aggregate rows (Total credits, Ending balance, …)
        desc_cell = "" if desc_col is None else (
            "" if pd.isna(r[desc_col]) else str(r[desc_col]))
        if _is_summary_row(desc_cell):
            skipped += 1
            continue

        # --- flag internal transfers (credit-card payments, etc.): keep the row
        # but mark it excluded from calculations so the user still sees it
        # (dimmed) and can re-include it.
        is_excluded = bool(exclude) and any(k in desc_cell.lower() for k in exclude)

        # --- date
        try:
            raw_date = r[date_col]
            dt = (pd.to_datetime(raw_date, format=date_fmt) if date_fmt
                  else pd.to_datetime(raw_date))
            date = dt.date().isoformat()
        except Exception:
            skipped += 1
            continue

        # --- amount (single signed col, or debit/credit pair)
        if amount_col is not None:
            amt = _clean_amount(r[amount_col])
            if amt is None:
                skipped += 1
                continue
            # Normalize so spend is always negative internally. When the column
            # is already signed, its signs are authoritative (see above).
            if not amount_already_signed and not spend_neg:
                amt = -amt
        else:
            debit = _clean_amount(r[debit_col]) if debit_col is not None else None
            credit = _clean_amount(r[credit_col]) if credit_col is not None else None
            if debit:
                amt = -abs(debit)
            elif credit:
                amt = abs(credit)
            else:
                skipped += 1
                continue

        # Amazon item totals represent spending even when listed positive.
        if source == "amazon" and amt > 0:
            amt = -amt

        # --- running balance (optional): keep it on the row (powers month-end
        # balance history for Net Worth accounts) AND remember the latest-dated
        # one as the statement's ending balance. Dates are ISO strings, so a
        # string compare orders them.
        bval = _clean_amount(r[balance_col]) if balance_col is not None else None
        if bval is not None and (statement_balance is None
                                 or date > statement_balance["date"]):
            statement_balance = {"amount": bval, "date": date}

        # Detect currency from the RAW amount cell (symbols survive here; they
        # are stripped by _clean_amount for the numeric parse above).
        raw_amount_cell = "" if amount_col is None else (
            "" if pd.isna(r[amount_col]) else str(r[amount_col]))
        ccy, ccy_source = _detect_currency(raw_amount_cell, desc_cell, file_default)

        desc = desc_cell
        rows.append({
            "date": date,
            "description": desc,
            "amount": amt,
            "category": categorize_fn(desc, category_rules),
            "source": source,
            "included": not is_excluded,
            "balance": bval,
            "currency": ccy,
            "currency_source": ccy_source,
        })
    if progress_cb:
        progress_cb(total_rows, total_rows)
    return rows, skipped, statement_balance


def parse_file_with_agent(file_bytes, filename, source, categorize_fn,
                          category_rules, model=DEFAULT_MODEL):
    """Top-level entry: read raw, ask the local agent for a spec, apply it.

    Returns (rows, warnings). Mirrors the signature style of the simple parser
    so app.py can call either.
    """
    warnings = []
    raw_df = _read_raw_table(file_bytes, filename)
    if raw_df.empty:
        return [], [f"{filename}: file appears empty."]

    sample = _sample_text(raw_df)
    spec = _call_ollama(model, sample, filename)
    rows, skipped, _ = _apply_spec(raw_df, spec, source, categorize_fn, category_rules)

    # The keyword rules above only tag descriptions that literally contain a
    # configured keyword. For everything still Uncategorized, ask the local
    # model to INFER a category from each description (bank/wire/merchant text).
    cat_names = [name for name, _ in (category_rules or [])]
    if cat_names and rows:
        unknown = sorted({
            r["description"] for r in rows
            if r["category"] == "Uncategorized" and r["description"].strip()
        })
        if unknown:
            try:
                mapping = categorize_with_agent(unknown, cat_names, model=model)
                for r in rows:
                    if r["category"] == "Uncategorized":
                        r["category"] = mapping.get(r["description"], "Uncategorized")
            except Exception as e:
                warnings.append(
                    f"{filename}: AI categorization unavailable ({e}); "
                    "kept keyword-rule categories."
                )

    if skipped:
        warnings.append(f"{filename}: skipped {skipped} unparseable row(s).")
    if not rows:
        warnings.append(
            f"{filename}: the agent could not extract rows. Detected spec: {spec}"
        )
    return rows, warnings


def propose_format(file_bytes, filename, model=DEFAULT_MODEL):
    """Ask the local agent to infer a layout for an UNKNOWN file and return it as
    registry-ready rules (column roles by header NAME, plus a match signature).

    Returns (proposal_dict, raw_df, header_row). The proposal has the same
    {source, match, parse} shape used in csv_formats.md, with an "identifier"
    suggestion the user can rename before saving.
    """
    raw_df = _read_raw_table(file_bytes, filename)
    if raw_df.empty:
        raise RuntimeError(f"{filename}: file appears empty.")

    spec = _call_ollama(model, _sample_text(raw_df, n=16), filename)
    header_row = int(spec.get("header_row", 0) or 0)
    if 0 <= header_row < len(raw_df):
        hdr_cells = [("" if pd.isna(v) else str(v)).strip()
                     for v in raw_df.iloc[header_row].tolist()]
    else:
        hdr_cells = []

    def name_at(idx):
        if idx is None:
            return None
        idx = int(idx)
        return hdr_cells[idx] or None if 0 <= idx < len(hdr_cells) else None

    start = header_row + 1
    amount_idx = spec.get("amount_col")
    already_signed = (amount_idx is not None
                      and _column_has_negative(raw_df, int(amount_idx), start))

    proposal = {
        "identifier": filename.rsplit(".", 1)[0],
        "source": "bank",
        "match": {
            "header_signature": [c for c in hdr_cells if c],
            "file_contains": [],
        },
        "parse": {
            "date_header": name_at(spec.get("date_col")),
            "desc_header": name_at(spec.get("desc_col")),
            "amount_header": name_at(spec.get("amount_col")),
            "debit_header": name_at(spec.get("debit_col")),
            "credit_header": name_at(spec.get("credit_col")),
            "amount_already_signed": bool(already_signed),
            "spend_is_negative": bool(spec.get("spend_is_negative", True)),
            "date_format": spec.get("date_format"),
            "skip_summary_rows": True,
        },
    }
    return proposal, raw_df, header_row


def check_ollama(model=DEFAULT_MODEL):
    """Health check used by the UI. Returns (ok: bool, message: str)."""
    try:
        req = urllib.request.Request("http://localhost:11434/api/tags")
        with urllib.request.urlopen(req, timeout=5) as resp:
            tags = json.loads(resp.read().decode())
        names = [m["name"] for m in tags.get("models", [])]
        if any(n.startswith(model) for n in names):
            return True, f"Ollama running; model '{model}' available."
        return False, (
            f"Ollama is running but '{model}' isn't pulled. Run: ollama pull {model}. "
            f"Available: {names or 'none'}"
        )
    except Exception as e:
        return False, (
            "Ollama not reachable at localhost:11434. Install from "
            f"https://ollama.com, then `ollama pull {model}`. ({e})"
        )


# ----------------------------------------------- local AI auto-categorization

CATEGORIZE_SYSTEM = (
    "You are a transaction categorizer. Given a list of merchant/description "
    "strings and a list of allowed category names, assign each description to "
    "the single best category. Use your knowledge of common merchants (e.g. "
    "'Chewy' and 'Petco' are pet/dog; 'Chipotle' is eating out; 'Whole Foods' "
    "is groceries). If none fit, use 'Uncategorized'. Respond with ONLY a JSON "
    "object mapping each description string to a category name — no prose."
)


def categorize_with_agent(descriptions, category_names, model=DEFAULT_MODEL,
                          batch_size=CATEGORIZE_BATCH, attempts=3, timeout=180,
                          progress_cb=None):
    """Use the LOCAL model to map merchant names -> categories.

    descriptions: list of unique description strings.
    category_names: list of allowed category names.
    Returns a dict {description: category}. Runs entirely on-machine; merchant
    names are processed locally and never sent to the web.

    Descriptions are processed in small batches so each request stays fast and
    well under the timeout, and every batch is retried on transient failures
    (see _post_chat_json). If a batch fails after all retries the error is
    raised, so the caller can surface it / offer a manual retry.
    """
    if not descriptions:
        return {}
    allowed = list(category_names) + ["Uncategorized"]
    valid = set(allowed)
    result = {}
    for start in range(0, len(descriptions), batch_size):
        batch = descriptions[start:start + batch_size]
        payload = {
            "model": model,
            "format": "json",
            "stream": False,
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": CATEGORIZE_SYSTEM},
                {
                    "role": "user",
                    "content": (
                        "Allowed categories: " + json.dumps(allowed)
                        + "\nDescriptions:\n" + json.dumps(batch)
                        + "\n\nReturn the JSON mapping."
                    ),
                },
            ],
        }
        mapping = _post_chat_json(payload, timeout=timeout, attempts=attempts)
        for d, c in mapping.items():
            result[d] = c if c in valid else "Uncategorized"
        if progress_cb:
            progress_cb(min(start + batch_size, len(descriptions)), len(descriptions))
    return result
