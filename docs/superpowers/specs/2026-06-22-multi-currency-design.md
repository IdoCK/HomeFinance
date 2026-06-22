# Multi-Currency — Design (Revised)

**Date:** 2026-06-22 · **Status:** Approved spine, ready for implementation plan.
**Supersedes the open decisions in** [`docs/multi-currency-plan/`](../../multi-currency-plan/00-CURRENCY-PLAN.md).
The three specialist docs (01 data model, 02 import detection, 03 frontend UX) remain the
detailed reference; **this doc overrides them wherever they conflict** — chiefly the canonical
base, the default display, and rate sourcing.

---

## 1. Goal

Users import statements in **any** currency; the system records each amount in its **original
currency** and converts using the rate **on that transaction's date**; users toggle the on-screen
display between **$ USD** and **₪ ILS**. Import **detects** the currency from statements where it
can. The app **functions fully offline if needed**, but may reach the web for rate data when
useful — under a strict data-minimization rule (§3).

## 2. Locked decisions (revised)

| Area | Decision | Change vs. original plan |
|---|---|---|
| **Canonical pivot** | **USD** — `amount_base` stored in USD; all aggregation sums USD | was ILS |
| **Default display** | **USD** | was ILS |
| **Display toggle** | Two options only: `$ USD \| ₪ ILS` | unchanged |
| **Stored currencies** | **Any ISO-4217** per row/account/budget/goal; original always indicated | unchanged intent, explicit |
| **Rate sourcing** | **Live per-date web fetch, cached in `fx_rates`**; manual entry as offline override | was bundled offline seed CSV (`data/fx_seed.csv` — now dropped) |
| **Rate provider** | **Frankfurter** (ECB daily reference, free, no API key, historical-by-date) | new |
| **Legacy data (340 rows)** | **USD** — confirmed in data (US payroll/wires/Zelle) | was assumed |
| **Migration backfill** | Trivial: `currency='USD'`, `amount_base = amount`, **no rate lookups** | greatly simplified |
| **Import contract** | importer writes `original amount`, `currency`, `currency_source`; **never converts** | unchanged |
| **Net Worth / reconciliation** | shown in **native** currency to avoid FX-rounding false discrepancies | unchanged |
| **New files** | `modules/fx.py`, `backend/api/fx.py`, `web/src/lib/currency.tsx` | `data/fx_seed.csv` removed |

## 3. Privacy invariant (the governing directive)

Local-first is **relaxed but data-minimized**, not abandoned:

1. **The app must work with no network** — only the *automatic* fetch of a missing rate is
   unavailable offline; manual rate entry covers that gap, and all conversion math is local.
2. **Outbound requests carry the minimum necessary and nothing else.** A rate fetch sends only
   `(date, base currency, quote currency)`. **No amounts, descriptions, account names, person
   identity, or any personal/financial data ever leaves the device.**
3. **All conversion is computed locally** from the fetched public rate. The web is a source of
   *rates*, never a calculator we hand our ledger to.
4. **Fetch only if needed.** Never fetch a rate we already have cached; never fetch for a
   USD-only operation; never background-poll. A fetch happens at import-time for a non-USD row's
   date, on an explicit "Refresh rates," or when a display conversion needs a date not yet cached.

## 4. Architecture

```
Import (detect currency per row) ─► transactions{ amount(original), currency, currency_source, amount_base(USD) }
                                          │ write-time: fx.to_base() converts original→USD
                   fx_rates(rate_date, base='USD', quote, rate, source, fetched_at)
                                          ▲ live fetch (Frankfurter) per needed date → cached, reused forever
Analytics sum amount_base (USD) ─► API ─► UI converts USD→display($|₪) at the render edge
```

- **USD rows** (today's entire DB, and most future activity): `amount_base == amount`. No
  conversion, no network, no drift — ever.
- **Non-USD rows** (e.g. an Israeli ₪ statement): `to_base()` looks up the USD/ILS rate for the
  txn date; on a cache miss it fetches once from Frankfurter, stores it in `fx_rates`, and reuses
  it forever.
- **Display toggle** ($↔₪): a render-edge multiply. "Current" aggregates (totals, net worth,
  budgets) convert USD→display at **today's** rate; the immutable transaction ledger converts each
  row at **its own txn-date** rate. *Sum first, round last.*

## 5. Data model

Per [`01-datamodel-fx.md`](../../multi-currency-plan/01-datamodel-fx.md), with **base = USD**:

```sql
-- transactions (additive, idempotent ALTER, mirrors existing init_db migration pattern)
ALTER TABLE transactions ADD COLUMN currency        TEXT NOT NULL DEFAULT 'USD'; -- ISO-4217, ORIGINAL entry currency
ALTER TABLE transactions ADD COLUMN currency_source TEXT NOT NULL DEFAULT 'legacy';
ALTER TABLE transactions ADD COLUMN amount_base     REAL;                        -- USD, derived at write-time; NULL until resolved

-- same currency column on the net-worth / planning tables so the toggle is global
ALTER TABLE accounts          ADD COLUMN currency TEXT NOT NULL DEFAULT 'USD';
ALTER TABLE balance_snapshots ADD COLUMN currency TEXT NOT NULL DEFAULT 'USD';
ALTER TABLE budgets           ADD COLUMN currency TEXT NOT NULL DEFAULT 'USD';
ALTER TABLE goals             ADD COLUMN currency TEXT NOT NULL DEFAULT 'USD';

CREATE TABLE IF NOT EXISTS fx_rates (
    rate_date  TEXT NOT NULL,                    -- ISO YYYY-MM-DD (reference/business day)
    base       TEXT NOT NULL,                    -- 'USD'
    quote      TEXT NOT NULL,                    -- 'ILS', ...
    rate       REAL NOT NULL,                    -- quote units per 1 base (1 USD = rate ILS)
    source     TEXT NOT NULL DEFAULT 'frankfurter', -- 'frankfurter' | 'manual'
    fetched_at TEXT,
    PRIMARY KEY (rate_date, base, quote)
);
CREATE INDEX IF NOT EXISTS idx_fx_lookup ON fx_rates(base, quote, rate_date);
```

- `amount` keeps its meaning: the number on the statement, in `currency`. `amount_base` is the
  derived USD value summed by every aggregation. Nullable so an unresolved row is detectable.
- Store one direction (`base='USD'`) and invert in code for the reverse pair.
- **Lookup rule** (unchanged): `WHERE base=? AND quote=? AND rate_date <= ? ORDER BY rate_date
  DESC LIMIT 1` → exact day, else nearest prior business day. On a miss, fetch that date; if the
  fetch is unavailable (offline) flag the row `rate_stale`/`rate_missing` and never crash.

## 6. FX engine — `modules/fx.py` (new)

```python
def get_rate(rate_date: str, base: str, quote: str) -> float | None   # §5 lookup; None if absent & offline
def fetch_rate(rate_date: str, base: str, quote: str) -> float | None  # Frankfurter; minimal egress (§3); caches
def to_base(amount: float, currency: str, on_date: str) -> float | None # original → USD (USD passthrough)
def convert(amount_base_usd: float, display: str, on_date: str | None) -> float  # USD → $|₪ at edge
def resolve_rows(rows: list[dict]) -> list[dict]   # fill amount_base, set rate_stale/rate_missing
def upsert_rate(rate_date, base, quote, rate, source='manual') -> None
```

- `fetch_rate` calls `https://api.frankfurter.dev/v1/{date}?base={base}&symbols={quote}`, parses
  the single rate, `upsert`s it (`source='frankfurter'`, `fetched_at=now`), returns it. It is the
  **only** network path; it sends only `(date, base, quote)` (§3). Frankfurter returns the nearest
  prior business day for weekends/holidays, which matches our lookup semantics.
- `get_rate` is pure-DB and offline-safe; the engine only calls `fetch_rate` on a cache miss, and
  conversion always falls back to flagging the row rather than blocking.

## 7. Import detection

Per [`02-import-detection.md`](../../multi-currency-plan/02-import-detection.md), unchanged except:
the **person/file default fallback is `USD`** (matches the household's actual dominant currency and
is the safer assumption for an undetectable row). Detection precedence stays: explicit currency
column → cell symbol/ISO code → registry `default_currency` → statement metadata → person default
(`USD`) → **unknown (blocks commit)**. Importer writes `currency` + `currency_source`; conversion to
`amount_base` happens server-side at commit via `fx.to_base()`.

## 8. Frontend

Per [`03-frontend-ux.md`](../../multi-currency-plan/03-frontend-ux.md), with these overrides:

- `web/src/lib/currency.tsx` `CurrencyProvider`, `localStorage["hf-currency"]`, **default `"USD"`**.
- Top-bar segmented pill `$ USD | ₪ ILS` (USD listed first / default-active).
- `web/src/components/money.tsx` becomes currency-aware (`formatMoney(n, currency)`, `<Money>`
  reads `useCurrency()`); original-currency markers in `--fl-muted`; missing/`rate_stale` states
  show the **original** native amount with an info-tone affordance, never a wrong zero.
- **Converted-shape contract = A (pre-converted)**: API returns each money record already converted
  for the active display plus `original_amount` + `currency`, so the toggle is instant.

## 9. Migration

1. Add columns (defaults above). Stamp legacy rows explicitly: `UPDATE transactions SET
   currency='USD', currency_source='legacy', amount_base = amount WHERE amount_base IS NULL`.
   **No rate lookups, no network** — all legacy data is USD = base.
2. Same `currency='USD'` stamp for `accounts` / `balance_snapshots` / `budgets` / `goals`.
3. A "Recompute base values" maintenance action (P2) re-runs `fx.resolve_rows()` after a rate
   refresh — only ever touches non-USD rows.

## 10. Phasing

**P0 — ledger + FX core (mostly offline)**
- `modules/database.py`: additive migrations (`currency`, `currency_source`, `amount_base` on
  `transactions`; `fx_rates` + index); trivial USD backfill (§9).
- `modules/fx.py` (new): `get_rate`, `to_base`, `convert`, `resolve_rows`, `upsert_rate`,
  `fetch_rate` (Frankfurter, data-minimized).
- `backend/schemas.py`: `ImportRow += currency, currency_source`.
- `backend/api/imports.py::commit` + `database.add_transactions`: write `currency`/source, resolve
  `amount_base` at write-time.
- `agent_parser._detect_currency` + `_apply_spec` emit currency (signals: column, cell symbol/code,
  person default = USD).
- Tests: USD passthrough (no network), ILS row converts via a mocked `fetch_rate`, offline miss →
  `rate_missing`, legacy backfill leaves USD untouched.

**P1 — display + toggle**
- `web/src/lib/currency.tsx`, `App.tsx` wrap, currency-aware `money.tsx`, top-bar pill (default USD).
- `backend/api/fx.py` (new): `GET /fx/rates`, `PUT /fx/rates` (manual override), `POST /fx/refresh`
  (explicit fetch of recent/needed dates).
- API boundary (`overview.py`, `budgets.py`, `networth.py`, `transactions.py`): return pre-converted
  display values + originals (shape A). `analytics.py` signatures unchanged (callers pass
  `amount_base`).
- Re-express Overview / Budgets / Recurring / Goals / NetWorth; transactions Amount + Original cols.
- Settings: default-currency control + read-only FX inspect (source, last fetched, range).

**P2 — coverage + polish**
- Import review-step Currency column, per-row override, "Set all", block-on-unknown; migrate FastAPI
  `/parse` to registry-first so `default_currency` applies.
- Currency on account/budget/goal create/update + input symbol adornments; native-currency Net-Worth
  reconciliation; "Recompute base values" action; `rate_stale` badge; transactions currency filter.

## 11. Resolved open questions

1. Canonical base / default display → **USD** (data is USD-dominant). ✔
2. Legacy data currency → **USD**, confirmed in DB. ✔
3. Rate sourcing → **live per-date fetch (Frankfurter), cached**, manual override; data-minimized. ✔
4. Seed depth → **N/A** (no bundle; fetch dates on demand). ✔
5. Currency scope → store any ISO; **display toggle = $/₪ only**. ✔
