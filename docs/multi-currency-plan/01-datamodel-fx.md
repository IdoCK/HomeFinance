# Multi-Currency: Data Model & FX Plan

**Status:** PLANNING ONLY (no source changed). Author: backend/fintech architect.
**Scope:** schema, conversion engine, rate sourcing under local-first, migration, phasing.
**Owns:** the data contract the import-side currency-recognition sibling agent writes into.

---

## 0. Context & guiding principles

HomeFinance stores transactions in a single SQLite file (`data/finance.db`) via
`modules/database.py`. Amounts are a single `REAL` column (`transactions.amount`,
negative = spend) with **no currency column today** — everything is implicitly one
currency (de-facto USD, given the USD-shaped starter taxonomy in
`_STARTER_CATEGORIES`). Net-worth accounts (`accounts.balance`,
`balance_snapshots.balance`) and budgets (`budgets.amount`) are likewise
currency-blind. All analytics (`modules/analytics.py`) operate on **lists of txn
dicts**, so any field we add to a row flows through `_df()` / `_split()`
unchanged — this is the lever we exploit.

Design principles:

1. **Store original, derive display.** Never overwrite the user's entered amount.
   Persist the original amount + currency; compute display values on read.
2. **One canonical base for math, two display currencies.** Pick **ILS as the
   canonical/base currency** (the household is Israel-based: NIS↔USD toggle, BOI
   is the natural rate source). Aggregations are summed in base, then converted
   once to the requested display currency. This avoids cross-rate drift.
3. **Local-first is non-negotiable.** No live FX API on the hot path. Rates are
   seeded data + explicit user-triggered fetch (opt-in). See §3.
4. **Rate-on-the-transaction-day.** A txn dated `D` in `quote=USD` converts with
   the (ILS,USD) rate for `D` (exact day, else nearest *prior* business day).

---

## 1. Schema changes

### 1.1 `transactions` — store original amount + currency

Add two columns (additive migration, safe on existing DBs — mirrors the existing
`PRAGMA table_info` migration pattern in `init_db()`):

```
ALTER TABLE transactions ADD COLUMN currency  TEXT NOT NULL DEFAULT 'ILS';  -- ISO-4217, the ORIGINAL entry currency
ALTER TABLE transactions ADD COLUMN amount_base REAL;                       -- amount converted to base (ILS) at txn-day rate; NULL until resolved
```

- `amount` keeps its meaning: the number the user/statement actually shows, in
  `currency`. The sibling import agent writes `currency` (and may pre-fill
  `amount_base` if it already resolved a rate; otherwise leaves it NULL).
- `amount_base` is the **derived** ILS value, cached at write-time (see §2). It is
  the single field every aggregation sums. Nullable so a freshly imported row with
  no rate yet is detectable and backfillable.
- Keep `balance` (running statement balance) in the row's **original** currency;
  add `balance_base REAL` only if net-worth-from-statements (`month_end_balances`)
  must be cross-currency — defer to P2.

The same pattern (currency + *_base) applies to net-worth so the toggle is global:

```
ALTER TABLE accounts          ADD COLUMN currency TEXT NOT NULL DEFAULT 'ILS';
ALTER TABLE balance_snapshots ADD COLUMN currency TEXT NOT NULL DEFAULT 'ILS';
ALTER TABLE budgets           ADD COLUMN currency TEXT NOT NULL DEFAULT 'ILS';
ALTER TABLE goals             ADD COLUMN currency TEXT NOT NULL DEFAULT 'ILS';  -- target_amount/saved_amount currency
```

Accounts/snapshots/budgets/goals convert at **query time** (their balances are
"current", not dated like a transaction) — see §2.3.

### 1.2 `fx_rates` table

```
CREATE TABLE IF NOT EXISTS fx_rates (
    rate_date TEXT NOT NULL,        -- ISO YYYY-MM-DD (the reference/business day)
    base      TEXT NOT NULL,        -- ISO-4217, e.g. 'ILS'
    quote     TEXT NOT NULL,        -- ISO-4217, e.g. 'USD'
    rate      REAL NOT NULL,        -- units of `quote` per 1 unit of `base`  (1 base = `rate` quote)
    source    TEXT NOT NULL DEFAULT 'seed',  -- 'seed' | 'boi' | 'ecb' | 'manual'
    fetched_at TEXT,                -- ISO timestamp when sourced (audit)
    PRIMARY KEY (rate_date, base, quote)
);
CREATE INDEX IF NOT EXISTS idx_fx_lookup ON fx_rates(base, quote, rate_date);
```

- **Uniqueness:** `(rate_date, base, quote)`. Store only one direction
  (`base='ILS'`) and invert in code for the reverse pair — halves storage and
  guarantees a single round-trip-consistent rate. (i.e. don't store both ILS→USD
  and USD→ILS; derive `usd_per_ils = 1/ils_per_usd`.)
- Keep `base` fixed at `'ILS'` in practice; the column exists for future pairs.

### 1.3 Lookup rule (exact day, else nearest prior business day)

`get_rate(rate_date, base, quote)`:
1. Normalize: if `base==quote` → `1.0`. If the pair is stored inverted
   (`quote==base_canonical`) → fetch canonical and return `1/rate`.
2. `SELECT rate FROM fx_rates WHERE base=? AND quote=? AND rate_date <= ?
   ORDER BY rate_date DESC LIMIT 1` — this gives **exact day if present, else the
   nearest prior** available reference day (weekends/holidays have no row, so the
   Friday/last-business-day rate carries forward — correct behavior for daily
   reference rates).
3. If **nothing** on or before `rate_date` (txn older than seeded history) → fall
   back to the **earliest** available rate and flag the row `rate_stale=1` in the
   API response (don't silently mislead). Never crash; never call the network here.

---

## 2. Conversion engine

### 2.1 Where conversion happens

**Hybrid, leaning write-time for transactions:**

- **Transactions → write-time (cached `amount_base`).** A txn's date is fixed, so
  its base value never changes once the rate exists. Resolve `amount_base` on
  import/commit (`backend/api/imports.py::commit`, `database.add_transactions`).
  This keeps all analytics fast and unchanged in shape — they just sum
  `amount_base` instead of `amount`.
- **Base → display currency → query-time.** The NIS↔USD toggle is a *display*
  concern; converting base→display at query time is one multiply per aggregate
  and lets the toggle be instant without rewriting stored data.

New module: **`modules/fx.py`** (pure, DB-backed lookups + conversion helpers):
```
def get_rate(rate_date: str, base: str, quote: str) -> float        # §1.3 rule
def to_base(amount: float, currency: str, on_date: str) -> float    # original -> ILS
def convert(amount_base: float, display: str, on_date: str|None) -> float
def resolve_rows(rows: list[dict]) -> list[dict]                    # fill amount_base, set rate_stale
```

### 2.2 Mixed-currency aggregation & the display layer

- Every analytics function already takes txn dicts. **Minimal change:** feed it
  `amount` = `amount_base` (ILS) so refund-netting, `_split`, transfer-pair
  matching, recurring detection all keep working in one currency. Do **not**
  scatter currency logic through `analytics.py`.
- At the **API boundary** (routers in `backend/api/`), accept a
  `display: Literal['ILS','USD'] = 'ILS'` query param. After analytics returns
  base-currency numbers, multiply each monetary field by
  `convert_factor = get_rate(today, 'ILS', display)` for "current" aggregates
  (totals, budgets, net worth) — a **single household-wide toggle**.
- **Per-transaction display** (the transactions list) uses each row's own
  txn-day rate to show its display value, so a 2-year-old USD charge shows the
  amount it really was in ILS-then or USD-original — expose both
  `amount` (original+`currency`) and `amount_base`, let the client format.

### 2.3 Toggle semantics across surfaces

| Surface | Base math | Display conversion | Rate date used |
|---|---|---|---|
| Overview totals / by_category (`overview.py`) | sum `amount_base` | × today's ILS→display | today (snapshot of value now) |
| Budgets (`budgets.py`) | spend in base vs cap in base | caps stored w/ `currency`→base; display × today | today |
| Net worth (`networth.py`) | sum balances→base | × today's ILS→display | today |
| Net-worth trend | per-snapshot base | × today's ILS→display | today (consistent series) |
| Transactions list | n/a | per-row txn-day rate | each txn's date |

Rationale: "what is my net worth **in USD**" means *today's* rate on a base total,
not a blend of historical rates. Only the immutable transaction ledger pins rate
to the transaction day (the explicit product requirement).

### 2.4 Rounding

- Store `amount_base` at **full float precision** (no rounding) — rounding only at
  the **display edge**, to 2 decimals, using banker's rounding consistently
  (match existing `round(x, 2)` calls). Summing rounded values causes penny drift;
  sum first, round last. Keep the existing `round(...,2)` in analytics outputs but
  ensure inputs (`amount_base`) are unrounded.

---

## 3. Rate sourcing under the local-first constraint (THE CRUX)

Live FX API calls on every render violate "nothing leaves this device." Options:

| Option | How | Pros | Cons |
|---|---|---|---|
| **A. Bundled offline historical dataset** | Ship `data/fx_seed.csv` (BOI/ECB daily ILS↔USD, e.g. last 10–15 yrs) seeded into `fx_rates` at `init_db()` | Zero network ever; covers virtually all real txns; deterministic | ~3–4k rows/decade (tiny); goes stale for *recent* days; must refresh the bundle per release |
| **B. Manual user entry** | UI to type a rate for a date; `source='manual'` | Pure local; user control | Tedious; error-prone; gaps |
| **C. Opt-in one-time fetch** | A button: "Update exchange rates" → one explicit HTTPS call to BOI/ECB, writes rows, then offline again | Fills the recency gap; still no background traffic; user consents each time | Requires network *that moment*; needs clear UX that this leaves the device |
| **D. Ship ECB/BOI daily reference with app** | Same as A but as a maintained data package updated each release | Curated, trustworthy source | Same staleness; release-coupled |

**Recommendation: A + C (D-flavored seed).**
- **Seed** a bundled BOI ILS↔USD daily history (`source='seed'`) at first run —
  covers all historical imports with **zero network**, preserving the promise by
  default.
- Provide an **explicit, opt-in "Refresh rates" action** (C) that the user
  triggers manually for recent dates. It is the *only* code path that touches the
  network, is clearly labeled "this contacts the Bank of Israel," off by default,
  and writes `source='boi'`. Manual entry (B) remains as a last-resort gap-filler.
- This satisfies local-first (nothing leaves the device unless the user
  explicitly clicks Refresh) while solving daily-historical coverage.

**Seeding/update mechanics:**
- `init_db()` (or a one-shot in `modules/fx.py::seed_rates()`) bulk-inserts the
  CSV with `INSERT OR IGNORE` keyed on the PK — idempotent, never clobbers
  user/manual rows.
- Refresh fetches only `[max(rate_date)+1 .. today]`, upserts, records
  `fetched_at`. Source endpoints: BOI exchange-rate API / ECB SDMX daily CSV
  (parse offline after the single fetch).

---

## 4. Migration of existing `data/finance.db`

Existing rows have no currency → an **implied single currency**.

- **Assumption (make it explicit & configurable):** existing data is **USD**
  (the starter taxonomy/keywords — `whole foods`, `mta`, `verizon` — are US). Do
  **not** silently assume ILS just because base is ILS.
- Expose a **one-time migration setting** `LEGACY_CURRENCY` (default `'USD'`,
  user-confirmable in UI before first multi-currency render) so a NIS-only
  household can pick `'ILS'`.
- Backfill, idempotent and safe:
  1. Add columns with `DEFAULT 'ILS'` (cheap), then **`UPDATE transactions SET
     currency = :LEGACY_CURRENCY WHERE amount_base IS NULL`** to stamp legacy rows
     with the chosen currency (don't trust the column default for legacy rows —
     set it deliberately).
  2. `fx.resolve_rows()` computes `amount_base` per row from its date + currency
     using seeded rates; rows older than seed history get earliest-rate +
     `rate_stale`.
  3. Same `LEGACY_CURRENCY` stamp for `accounts`/`balance_snapshots`/`budgets`/
     `goals`.
- Migration is **reversible in spirit**: original `amount`/`currency` untouched;
  only the derived `amount_base` is (re)computable. A "recompute base values"
  action lets the user re-run after a rate refresh.

---

## 5. Phasing — P0 / P1 / P2 (file paths + tiny signatures only)

### P0 — foundation (ledger correctness)
- `modules/database.py`: add migrations (`currency`, `amount_base` on
  `transactions`; `fx_rates` table + index); `seed_rates()` call in `init_db()`.
  - `def get_rate(rate_date, base, quote) -> float`
  - `def upsert_rate(rate_date, base, quote, rate, source) -> None`
- `modules/fx.py` (NEW): `to_base`, `convert`, `resolve_rows`, `seed_rates`.
- `data/fx_seed.csv` (NEW, bundled BOI ILS↔USD daily history).
- `backend/api/imports.py::commit` + `database.add_transactions`: resolve
  `amount_base` at write-time; `backend/schemas.py::ImportRow` gains
  `currency: str = 'ILS'` (the import-agent contract).
- One-time backfill + `LEGACY_CURRENCY` config (`modules/database.py` migration).

### P1 — display & toggle
- `backend/schemas.py`: `display: Literal['ILS','USD'] = 'ILS'` shared param.
- `backend/api/overview.py`, `budgets.py`, `networth.py`, `transactions.py`:
  accept `display`, convert base→display via `fx.convert` at the boundary;
  transactions list returns `amount`,`currency`,`amount_base`,`rate_stale`.
- `analytics.py`: **no signature change** — callers pass `amount_base` as
  `amount`. (Verify `_split`/refund logic still sign-correct.)
- New endpoints: `GET /fx/rates`, `PUT /fx/rates` (manual), `POST /fx/refresh`
  (opt-in fetch) — `backend/api/fx.py` (NEW router).

### P2 — polish & coverage
- Currency on `accounts`/`budgets`/`goals` create/update schemas + UI.
- `balance_base` for statement-derived net worth (`month_end_balances`,
  `reconcile` cross-currency awareness).
- "Recompute base values" maintenance action after a rate refresh.
- Stale-rate UI badge; additional pairs (EUR) — schema already supports.

---

## 6. Open questions for product
1. Confirm **ILS as canonical base** (vs USD) — affects seed direction & rounding.
2. Confirm **legacy data = USD** default for migration.
3. Is the household single-base (one toggle) acceptable, or per-person display?
4. Acceptable seed history depth (10 yrs vs full BOI history ~1990s)?
