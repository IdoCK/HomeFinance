# Multi-Currency P0 — Ledger + FX Core Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every transaction an original currency + a USD `amount_base`, with a DB-backed FX rate table fed by an on-demand, data-minimized web fetch — all behind the existing import flow, with **no visible UI change yet**.

**Architecture:** Additive SQLite migration adds `currency`/`currency_source`/`amount_base` to `transactions` and a `fx_rates` table. A new pure module `modules/fx.py` does rate lookup (DB-only, offline-safe), an opt-in `fetch_rate` (Frankfurter, sends only date+currency pair), and original→USD conversion. Import commit resolves `amount_base` at write time. All 340 existing rows backfill trivially as USD (`amount_base = amount`), so no rate lookups touch legacy data.

**Tech Stack:** Python 3.12, SQLite (`sqlite3`), FastAPI, pydantic v2, pytest (in `venv`), pandas (import parser), `urllib.request` (matches existing no-dependency HTTP style in `agent_parser.py`).

## Global Constraints

- **Canonical pivot = USD.** `amount_base` is always USD. USD rows store `amount_base == amount` with no conversion.
- **Default currency on every new column = `'USD'`** (DDL default), and legacy rows are stamped `currency='USD'`, `currency_source='legacy'` explicitly.
- **Data-minimization (hard rule):** the only outbound call is `fx.fetch_rate`, and its request carries **only** `(date, base, quote)`. No amounts, descriptions, person, or account data ever leaves the device. All conversion math is local.
- **Offline-safe:** `get_rate`/`to_base`/`convert` never raise on a missing rate or network failure — they return `None`/flag `rate_stale`, never crash, never block a commit.
- **Migrations are additive + idempotent**, guarded by `PRAGMA table_info`, mirroring the existing pattern in `modules/database.py::init_db` (lines 220–238).
- **Rates stored one direction only:** `base='USD'`, `quote` ∈ {`ILS`,…}; invert in code for the reverse pair.
- Run Python tests with: `venv/Scripts/python -m pytest <path> -v` (from repo root, Git Bash).

---

### Task 1: Schema migration — currency columns + `fx_rates` table + USD backfill

**Files:**
- Modify: `modules/database.py:60-238` (`init_db`, additive migration block)
- Test: `tests/test_fx_migration.py` (create)

**Interfaces:**
- Consumes: existing `init_db()`, `get_conn()`.
- Produces: `transactions.currency` (TEXT NOT NULL DEFAULT 'USD'), `transactions.currency_source` (TEXT NOT NULL DEFAULT 'legacy'), `transactions.amount_base` (REAL, nullable), `fx_rates` table with PK `(rate_date, base, quote)` and index `idx_fx_lookup`. After `init_db()`, every pre-existing transaction row has `currency='USD'`, `currency_source='legacy'`, `amount_base = amount`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fx_migration.py
import sqlite3
from modules import database


def _seed_legacy_row(db_path):
    """Insert a transaction the OLD way (no currency columns) to simulate a
    pre-migration DB, then run init_db to migrate it."""
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS people(id INTEGER PRIMARY KEY, name TEXT);
           CREATE TABLE IF NOT EXISTS transactions(
             id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER, date TEXT,
             description TEXT, amount REAL, category TEXT, source TEXT,
             included INTEGER DEFAULT 1, balance REAL);"""
    )
    conn.execute("INSERT INTO people(id,name) VALUES (1,'Ido')")
    conn.execute(
        "INSERT INTO transactions(person_id,date,description,amount) "
        "VALUES (1,'2026-03-13','ILLUMINA PAYROLL',3684.08)")
    conn.commit()
    conn.close()


def test_migration_adds_columns_and_backfills_usd(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    _seed_legacy_row(db_path)

    database.init_db()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cols = {r[1] for r in conn.execute("PRAGMA table_info(transactions)")}
    assert {"currency", "currency_source", "amount_base"} <= cols

    row = conn.execute("SELECT * FROM transactions WHERE description='ILLUMINA PAYROLL'").fetchone()
    assert row["currency"] == "USD"
    assert row["currency_source"] == "legacy"
    assert row["amount_base"] == 3684.08  # USD pivot: base == amount

    fx_cols = {r[1] for r in conn.execute("PRAGMA table_info(fx_rates)")}
    assert {"rate_date", "base", "quote", "rate", "source", "fetched_at"} <= fx_cols
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python -m pytest tests/test_fx_migration.py -v`
Expected: FAIL — `currency` not in columns (KeyError / assert fails).

- [ ] **Step 3: Add the migration block**

In `modules/database.py::init_db`, immediately after the existing balance migration (`if "balance" not in cols:` block ending line 238), append:

```python
        # Migration: multi-currency. `currency` = the ORIGINAL entry currency
        # (ISO-4217); `currency_source` records which detection signal set it;
        # `amount_base` is the value in the canonical pivot (USD), derived at
        # write-time. Legacy rows are all USD (US-bank data), so base == amount.
        cols = [r[1] for r in c.execute("PRAGMA table_info(transactions)")]
        if "currency" not in cols:
            c.execute("ALTER TABLE transactions ADD COLUMN currency TEXT NOT NULL DEFAULT 'USD'")
        if "currency_source" not in cols:
            c.execute("ALTER TABLE transactions ADD COLUMN currency_source TEXT NOT NULL DEFAULT 'legacy'")
        if "amount_base" not in cols:
            c.execute("ALTER TABLE transactions ADD COLUMN amount_base REAL")
            # Backfill legacy rows: all USD, so base == amount. No rate lookups.
            c.execute("UPDATE transactions SET currency='USD', currency_source='legacy', "
                      "amount_base=amount WHERE amount_base IS NULL")

        # Currency on the net-worth / planning tables so the display toggle is
        # global. All existing data is USD.
        for tbl in ("accounts", "balance_snapshots", "budgets", "goals"):
            tcols = [r[1] for r in c.execute(f"PRAGMA table_info({tbl})")]
            if "currency" not in tcols:
                c.execute(f"ALTER TABLE {tbl} ADD COLUMN currency TEXT NOT NULL DEFAULT 'USD'")

        # FX rates: one direction only (base='USD'); invert in code for reverse.
        c.execute(
            """CREATE TABLE IF NOT EXISTS fx_rates (
                   rate_date  TEXT NOT NULL,
                   base       TEXT NOT NULL,
                   quote      TEXT NOT NULL,
                   rate       REAL NOT NULL,
                   source     TEXT NOT NULL DEFAULT 'frankfurter',
                   fetched_at TEXT,
                   PRIMARY KEY (rate_date, base, quote)
               )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_fx_lookup ON fx_rates(base, quote, rate_date)")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python -m pytest tests/test_fx_migration.py -v`
Expected: PASS.

- [ ] **Step 5: Run the full Python suite to confirm no regression**

Run: `venv/Scripts/python -m pytest tests/ -q`
Expected: all pass (existing tests unaffected — columns are additive with defaults).

- [ ] **Step 6: Commit**

```bash
git add modules/database.py tests/test_fx_migration.py
git commit -m "feat(db): multi-currency schema migration + USD legacy backfill"
```

---

### Task 2: `modules/fx.py` — rate lookup + upsert (DB-only, offline-safe)

**Files:**
- Create: `modules/fx.py`
- Test: `tests/test_fx_lookup.py` (create)

**Interfaces:**
- Consumes: `database.get_conn()`, `database.DB_PATH` (so tests' monkeypatch applies).
- Produces:
  - `upsert_rate(rate_date: str, base: str, quote: str, rate: float, source: str = "manual") -> None`
  - `get_rate(rate_date: str, base: str, quote: str) -> float | None` — exact day, else nearest *prior* row; `base==quote` → `1.0`; inverted pair → `1/stored`; `None` if nothing on/before date and nothing to fetch (no network here).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fx_lookup.py
from modules import database, fx


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "t.db")
    database.init_db()


def test_same_currency_is_identity(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    assert fx.get_rate("2026-03-13", "USD", "USD") == 1.0


def test_upsert_and_exact_lookup(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    fx.upsert_rate("2026-03-13", "USD", "ILS", 3.60, source="manual")
    assert fx.get_rate("2026-03-13", "USD", "ILS") == 3.60


def test_nearest_prior_business_day(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    fx.upsert_rate("2026-03-13", "USD", "ILS", 3.60)  # Friday
    # Sat/Sun have no row; Saturday lookup carries Friday forward.
    assert fx.get_rate("2026-03-14", "USD", "ILS") == 3.60


def test_inverse_pair_is_derived(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    fx.upsert_rate("2026-03-13", "USD", "ILS", 4.0)
    assert fx.get_rate("2026-03-13", "ILS", "USD") == 0.25  # 1/4


def test_missing_rate_returns_none(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    assert fx.get_rate("2026-03-13", "USD", "ILS") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python -m pytest tests/test_fx_lookup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'modules.fx'`.

- [ ] **Step 3: Write the module**

```python
# modules/fx.py
"""Foreign-exchange conversion for the household ledger.

Canonical pivot is USD: every transaction's `amount_base` is in USD, and USD
rows need no conversion at all. Rates live in the `fx_rates` table, one
direction only (base='USD'); the reverse pair is derived as 1/rate.

Privacy: the ONLY outbound network call is `fetch_rate`, and it sends only a
date and a currency pair (no amounts, no personal data). All conversion math is
local. Lookups (`get_rate`) are DB-only and never touch the network.
"""
from modules import database as db

PIVOT = "USD"


def upsert_rate(rate_date, base, quote, rate, source="manual"):
    """Insert/replace one rate row (PK = rate_date, base, quote)."""
    from datetime import datetime
    with db.get_conn() as conn:
        conn.execute(
            """INSERT INTO fx_rates(rate_date, base, quote, rate, source, fetched_at)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(rate_date, base, quote) DO UPDATE SET
                   rate=excluded.rate, source=excluded.source,
                   fetched_at=excluded.fetched_at""",
            (rate_date, base, quote, float(rate), source,
             datetime.now().isoformat(timespec="seconds")))


def _lookup(rate_date, base, quote):
    """Raw DB lookup: exact day else nearest prior. None if nothing on/before."""
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT rate FROM fx_rates WHERE base=? AND quote=? AND rate_date<=? "
            "ORDER BY rate_date DESC LIMIT 1", (base, quote, rate_date)).fetchone()
        return row[0] if row else None


def get_rate(rate_date, base, quote):
    """Rate to multiply `base` by to get `quote`, on `rate_date` (exact day else
    nearest prior business day). DB-only, offline-safe: returns None if absent."""
    if base == quote:
        return 1.0
    direct = _lookup(rate_date, base, quote)
    if direct is not None:
        return direct
    inverse = _lookup(rate_date, quote, base)
    if inverse:
        return 1.0 / inverse
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python -m pytest tests/test_fx_lookup.py -v`
Expected: PASS (all 5).

- [ ] **Step 5: Commit**

```bash
git add modules/fx.py tests/test_fx_lookup.py
git commit -m "feat(fx): DB-backed rate lookup + upsert (offline-safe)"
```

---

### Task 3: `fx.fetch_rate` — data-minimized Frankfurter fetch

**Files:**
- Modify: `modules/fx.py`
- Test: `tests/test_fx_fetch.py` (create)

**Interfaces:**
- Consumes: `upsert_rate`, `get_rate`.
- Produces:
  - `frankfurter_url(rate_date: str, base: str, quote: str) -> str` — builds the request URL; carries only date+base+quote.
  - `fetch_rate(rate_date: str, base: str, quote: str) -> float | None` — fetches once from Frankfurter, upserts (`source='frankfurter'`), returns the rate; `None` on any network/parse failure (never raises).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fx_fetch.py
from modules import database, fx


def test_url_carries_only_date_and_currencies():
    url = fx.frankfurter_url("2026-03-13", "USD", "ILS")
    assert url == "https://api.frankfurter.dev/v1/2026-03-13?base=USD&symbols=ILS"
    # Privacy invariant: nothing but the date + currency codes is present.
    for forbidden in ("amount", "3684", "ILLUMINA", "person", "Ido", "Aviv"):
        assert forbidden not in url


def test_fetch_rate_caches_and_returns(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "t.db")
    database.init_db()

    calls = []
    def fake_http(url):
        calls.append(url)
        return {"base": "USD", "date": "2026-03-13", "rates": {"ILS": 3.66}}
    monkeypatch.setattr(fx, "_http_get_json", fake_http)

    assert fx.fetch_rate("2026-03-13", "USD", "ILS") == 3.66
    # Cached now: a second get_rate must NOT trigger another fetch.
    assert fx.get_rate("2026-03-13", "USD", "ILS") == 3.66
    assert len(calls) == 1


def test_fetch_rate_returns_none_on_network_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "t.db")
    database.init_db()
    def boom(url):
        raise OSError("offline")
    monkeypatch.setattr(fx, "_http_get_json", boom)
    assert fx.fetch_rate("2026-03-13", "USD", "ILS") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python -m pytest tests/test_fx_fetch.py -v`
Expected: FAIL — `module 'modules.fx' has no attribute 'frankfurter_url'`.

- [ ] **Step 3: Add the fetch code to `modules/fx.py`**

```python
import json
import urllib.request

FRANKFURTER_BASE = "https://api.frankfurter.dev/v1"


def frankfurter_url(rate_date, base, quote):
    """Build the rate-request URL. Carries ONLY the date and currency pair —
    no amounts or personal data (the data-minimization invariant)."""
    return f"{FRANKFURTER_BASE}/{rate_date}?base={base}&symbols={quote}"


def _http_get_json(url):
    """Single GET → parsed JSON. Isolated so tests can stub the network."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def fetch_rate(rate_date, base, quote):
    """Fetch one rate from Frankfurter (ECB data), cache it, return it.

    The only network path in the app. Sends only (date, base, quote). On any
    failure returns None and never raises — the caller flags the row instead.
    Frankfurter returns the nearest prior business day for weekends/holidays;
    we store the rate under the REQUESTED date so repeat lookups hit the cache.
    """
    if base == quote:
        return 1.0
    try:
        data = _http_get_json(frankfurter_url(rate_date, base, quote))
        rate = data.get("rates", {}).get(quote)
        if rate is None:
            return None
        upsert_rate(rate_date, base, quote, float(rate), source="frankfurter")
        return float(rate)
    except Exception:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python -m pytest tests/test_fx_fetch.py -v`
Expected: PASS (all 3).

- [ ] **Step 5: Commit**

```bash
git add modules/fx.py tests/test_fx_fetch.py
git commit -m "feat(fx): data-minimized Frankfurter rate fetch with caching"
```

---

### Task 4: `fx.to_base` / `convert` / `resolve_rows` — conversion helpers

**Files:**
- Modify: `modules/fx.py`
- Test: `tests/test_fx_convert.py` (create)

**Interfaces:**
- Consumes: `get_rate`, `fetch_rate`, `PIVOT`.
- Produces:
  - `to_base(amount: float, currency: str, on_date: str) -> float | None` — original→USD. USD passthrough returns `amount` unchanged with no lookup. Non-USD: `get_rate` then `fetch_rate` on miss; `None` if still unresolved.
  - `convert(amount_base_usd: float, display: str, on_date: str | None) -> float | None` — USD→display at `on_date`'s rate (or today's if `on_date` None). USD passthrough.
  - `resolve_rows(rows: list[dict]) -> list[dict]` — fills `amount_base` for rows where it's None, sets `rate_stale=True` when conversion failed; mutates and returns the list.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fx_convert.py
from modules import database, fx


def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "t.db")
    database.init_db()


def test_usd_passthrough_no_network(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    monkeypatch.setattr(fx, "_http_get_json",
                        lambda url: (_ for _ in ()).throw(AssertionError("network called for USD")))
    assert fx.to_base(3684.08, "USD", "2026-03-13") == 3684.08


def test_non_usd_converts_to_usd(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    fx.upsert_rate("2026-03-13", "USD", "ILS", 4.0)  # 1 USD = 4 ILS
    # 400 ILS / 4 = 100 USD
    assert fx.to_base(400.0, "ILS", "2026-03-13") == 100.0


def test_to_base_fetches_on_miss(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    monkeypatch.setattr(fx, "_http_get_json",
                        lambda url: {"rates": {"ILS": 4.0}})
    assert fx.to_base(400.0, "ILS", "2026-03-13") == 100.0


def test_to_base_none_when_unresolvable(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    monkeypatch.setattr(fx, "_http_get_json",
                        lambda url: (_ for _ in ()).throw(OSError("offline")))
    assert fx.to_base(400.0, "ILS", "2026-03-13") is None


def test_convert_usd_to_display(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    fx.upsert_rate("2026-03-13", "USD", "ILS", 3.5)
    assert fx.convert(100.0, "USD", "2026-03-13") == 100.0
    assert fx.convert(100.0, "ILS", "2026-03-13") == 350.0


def test_resolve_rows_flags_stale(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    monkeypatch.setattr(fx, "_http_get_json",
                        lambda url: (_ for _ in ()).throw(OSError("offline")))
    rows = [{"amount": 100.0, "currency": "USD", "date": "2026-03-13", "amount_base": None},
            {"amount": 400.0, "currency": "ILS", "date": "2026-03-13", "amount_base": None}]
    out = fx.resolve_rows(rows)
    assert out[0]["amount_base"] == 100.0 and not out[0].get("rate_stale")
    assert out[1]["amount_base"] is None and out[1]["rate_stale"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python -m pytest tests/test_fx_convert.py -v`
Expected: FAIL — `module 'modules.fx' has no attribute 'to_base'`.

- [ ] **Step 3: Add the conversion helpers to `modules/fx.py`**

```python
from datetime import date as _date


def _rate_or_fetch(on_date, base, quote):
    """Cached rate, else one fetch, else None. Offline-safe."""
    r = get_rate(on_date, base, quote)
    if r is not None:
        return r
    return fetch_rate(on_date, base, quote)


def to_base(amount, currency, on_date):
    """Original amount in `currency` -> USD on `on_date`. USD passes through
    untouched (no lookup, no network). None if no rate could be resolved."""
    if amount is None:
        return None
    if currency == PIVOT:
        return amount
    rate = _rate_or_fetch(on_date, PIVOT, currency)  # USD->currency (quote per USD)
    if not rate:
        return None
    return amount / rate


def convert(amount_base_usd, display, on_date=None):
    """USD base -> display currency at `on_date` (today if None). USD passes
    through. None if the rate is unavailable."""
    if amount_base_usd is None:
        return None
    if display == PIVOT:
        return amount_base_usd
    on = on_date or _date.today().isoformat()
    rate = _rate_or_fetch(on, PIVOT, display)
    if not rate:
        return None
    return amount_base_usd * rate


def resolve_rows(rows):
    """Fill `amount_base` (USD) for rows where it's None; set rate_stale=True
    where conversion failed. Mutates and returns rows."""
    for r in rows:
        if r.get("amount_base") is not None:
            continue
        base = to_base(r.get("amount"), r.get("currency", PIVOT), r.get("date"))
        if base is None:
            r["amount_base"] = None
            r["rate_stale"] = True
        else:
            r["amount_base"] = base
            r["rate_stale"] = False
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python -m pytest tests/test_fx_convert.py -v`
Expected: PASS (all 6).

- [ ] **Step 5: Commit**

```bash
git add modules/fx.py tests/test_fx_convert.py
git commit -m "feat(fx): to_base/convert/resolve_rows conversion helpers"
```

---

### Task 5: Import contract — `ImportRow` currency fields + write `amount_base` at commit

**Files:**
- Modify: `backend/schemas.py:63-78` (`ImportRow`)
- Modify: `modules/database.py:255-269` (`add_transactions`)
- Modify: `backend/api/imports.py:47-53` (`commit`)
- Test: `tests/api/test_import_currency.py` (create)

**Interfaces:**
- Consumes: `fx.to_base`, the Task 1 schema.
- Produces: `ImportRow` gains `currency: str = "USD"`, `currency_source: str = "unknown"`. `add_transactions` persists `currency`, `currency_source`, `amount_base` (computed via `fx.to_base` when not supplied). `commit` resolves base server-side.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_import_currency.py
# Uses the shared client fixture in tests/api/conftest.py.

def test_commit_writes_currency_and_usd_base(client, monkeypatch):
    from modules import fx
    # No real network: stub the fetcher (USD rows shouldn't call it anyway).
    monkeypatch.setattr(fx, "_http_get_json",
                        lambda url: {"rates": {"ILS": 4.0}})
    people = client.get("/api/people").json()
    pid = people[0]["id"]

    body = {
        "person_id": pid, "filename": "boa.csv", "file_hash": "h1", "source": "bank",
        "rows": [
            {"date": "2026-03-13", "description": "ILLUMINA PAYROLL", "amount": 3684.08,
             "currency": "USD", "currency_source": "person_default"},
            {"date": "2026-03-13", "description": "SUPERMARKET TLV", "amount": 400.0,
             "currency": "ILS", "currency_source": "cell_symbol"},
        ],
    }
    assert client.post("/api/import/commit", json=body).json()["imported"] == 2

    txns = client.get("/api/transactions", params={"person_id": pid}).json()
    usd = next(t for t in txns if "ILLUMINA" in t["description"])
    ils = next(t for t in txns if "SUPERMARKET" in t["description"])
    assert usd["currency"] == "USD" and usd["amount_base"] == 3684.08   # passthrough
    assert ils["currency"] == "ILS" and ils["amount_base"] == 100.0     # 400/4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python -m pytest tests/api/test_import_currency.py -v`
Expected: FAIL — committed rows have no `currency`/`amount_base` (KeyError or wrong value).

- [ ] **Step 3a: Extend `ImportRow`** (`backend/schemas.py`)

```python
class ImportRow(BaseModel):
    date: str
    description: str
    amount: float
    category: str = "Uncategorized"
    source: str = "auto"
    included: bool = True
    balance: Optional[float] = None
    currency: str = "USD"
    currency_source: str = "unknown"
```

- [ ] **Step 3b: Persist the new fields** (`modules/database.py::add_transactions`)

```python
def add_transactions(person_id, rows, file_hash=None):
    """rows: list of dicts with keys date, description, amount, category, source,
    currency, currency_source, amount_base, and optional included (defaults to 1).
    file_hash links every row to the imported file (see imported_files)."""
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO transactions
               (person_id, date, description, amount, category, source,
                file_hash, included, balance, currency, currency_source, amount_base)
               VALUES (:person_id, :date, :description, :amount, :category,
                       :source, :file_hash, :included, :balance,
                       :currency, :currency_source, :amount_base)""",
            [{**r, "person_id": person_id, "file_hash": file_hash,
              "included": int(r.get("included", 1)),
              "balance": r.get("balance"),
              "currency": r.get("currency", "USD"),
              "currency_source": r.get("currency_source", "unknown"),
              "amount_base": r.get("amount_base")} for r in rows],
        )
```

- [ ] **Step 3c: Resolve base at commit** (`backend/api/imports.py::commit`)

```python
@router.post("/commit")
def commit(body: ImportCommit):
    from modules import fx
    rows = [r.model_dump() for r in body.rows]
    fx.resolve_rows(rows)  # fills amount_base (USD) per row's date+currency
    db.add_transactions(body.person_id, rows, file_hash=body.file_hash)
    db.record_import(body.person_id, body.file_hash, body.filename, len(rows),
                     datetime.now().strftime("%Y-%m-%d %H:%M"))
    return {"imported": len(rows)}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python -m pytest tests/api/test_import_currency.py -v`
Expected: PASS.

- [ ] **Step 5: Run the import + transactions API tests for regression**

Run: `venv/Scripts/python -m pytest tests/api/test_imports.py tests/api/test_transactions.py -q`
Expected: all pass (new fields have defaults; existing callers unaffected).

- [ ] **Step 6: Commit**

```bash
git add backend/schemas.py modules/database.py backend/api/imports.py tests/api/test_import_currency.py
git commit -m "feat(import): persist currency + resolve USD amount_base at commit"
```

---

### Task 6: Currency detection in the parser — `_detect_currency` + `_apply_spec` emit it

**Files:**
- Modify: `modules/agent_parser.py:166-178` (near `_clean_amount`), `:209-324` (`_apply_spec`)
- Test: `tests/test_currency_detect.py` (create)

**Interfaces:**
- Consumes: raw cell strings (pre-`_clean_amount`).
- Produces:
  - `_detect_currency(amount_cell: str, desc_cell: str, file_default: str | None) -> tuple[str, str]` → `(code, source)`. Precedence: cell symbol/ISO code (`₪`/`ILS`/`NIS`→`ILS`, `$`/`US$`/`USD`→`USD`, `€`/`EUR`→`EUR`) → `file_default` → person default `"USD"`. Returns `("USD","person_default")` when nothing else fires.
  - Each row dict from `_apply_spec` gains `"currency"` and `"currency_source"`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_currency_detect.py
from modules import agent_parser as ap


def test_shekel_symbol_detected():
    assert ap._detect_currency("₪400.00", "SUPERMARKET", None) == ("ILS", "cell_symbol")

def test_iso_code_in_cell():
    assert ap._detect_currency("400 ILS", "x", None) == ("ILS", "cell_code")

def test_dollar_symbol_detected():
    assert ap._detect_currency("$1,234.50", "x", None) == ("USD", "cell_symbol")

def test_file_default_used_when_no_signal():
    assert ap._detect_currency("400.00", "x", "ILS") == ("ILS", "file_default")

def test_person_default_usd_when_nothing():
    assert ap._detect_currency("400.00", "x", None) == ("USD", "person_default")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python -m pytest tests/test_currency_detect.py -v`
Expected: FAIL — `module 'modules.agent_parser' has no attribute '_detect_currency'`.

- [ ] **Step 3a: Add `_detect_currency`** (insert above `_clean_amount` in `modules/agent_parser.py`)

```python
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
```

- [ ] **Step 3b: Emit it from `_apply_spec`.** Change the signature to accept a `file_default`, and add the two keys to the row dict.

In `modules/agent_parser.py`, update the signature (line ~209):

```python
def _apply_spec(raw_df, spec, source, categorize_fn, category_rules,
                progress_cb=None, file_default=None):
```

Then, inside the row loop where the amount cell is read, capture the raw cell and detect currency just before building the row dict. Replace the `rows.append({...})` block (lines ~312-321) with:

```python
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python -m pytest tests/test_currency_detect.py -v`
Expected: PASS (all 5).

- [ ] **Step 5: Run the parser-adjacent suite for regression**

Run: `venv/Scripts/python -m pytest tests/ -q`
Expected: all pass (`file_default` defaults to None; row dict gains keys that `add_transactions` already tolerates).

- [ ] **Step 6: Commit**

```bash
git add modules/agent_parser.py tests/test_currency_detect.py
git commit -m "feat(import): per-row currency detection from raw cells"
```

---

## Self-Review

**Spec coverage (§5 P0 list, §6, §7, §9 of the design):**
- Schema migration (`currency`, `currency_source`, `amount_base`, `fx_rates`) → Task 1. ✔
- `modules/fx.py` (`get_rate`, `upsert_rate`, `fetch_rate`, `to_base`, `convert`, `resolve_rows`) → Tasks 2–4. ✔
- Live cached fetch via Frankfurter + data-minimization invariant → Task 3 (URL test asserts no PII). ✔
- `ImportRow` currency fields + write-time base resolution → Task 5. ✔
- Per-row detection (signals: cell symbol/code, file default, person default=USD) → Task 6. ✔
- Trivial USD legacy backfill, no rate lookups → Task 1 (Step 3, the `UPDATE`). ✔

**Deferred to P1/P2 (intentionally not in P0):** `backend/api/fx.py` router, `display` query params, registry `default_currency` / `csv_formats.md`, the live `/parse` path's `file_default` wiring + UI source-currency selector. P0 keeps `file_default=None` on the live path; detection still works via cell symbols and the USD person-default. No visible UI change ships in P0.

**Placeholder scan:** none — every step has full code and a runnable command.

**Type consistency:** `to_base`/`convert`/`resolve_rows`/`get_rate`/`fetch_rate`/`upsert_rate` signatures match between their defining task and their call sites (Task 5 `commit` uses `fx.resolve_rows`; Task 4 uses `get_rate`/`fetch_rate` from Tasks 2–3). `amount_base` is USD everywhere. `currency_source` default is `"unknown"` in the schema (row may be committed without detection) and `"legacy"` for migrated rows — distinct by design.
