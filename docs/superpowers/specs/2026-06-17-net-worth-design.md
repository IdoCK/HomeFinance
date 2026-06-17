# Net Worth (Hybrid) — Design

**Status:** Implemented (uncommitted) · **Date:** 2026-06-17 · **Wave:** 2 of the finance overhaul

> Built per this design: `accounts`/`balance_snapshots` tables + CRUD in
> `modules/database.py`; `net_worth`/`net_worth_trend` in `modules/analytics.py`;
> `balance_header`→`balance_col` capture in `modules/{formats,agent_parser}.py`
> (`_apply_spec` now returns a 3rd value, `statement_balance`); Net Worth tab,
> Dashboard KPI, and import-time auto-refresh in `app.py`. Tests in
> `tests/test_networth.py` (analytics + DB smoke + statement-balance capture).

## Goal

Answer "are we building wealth?" by showing household **net worth** = total assets − total
liabilities, with a trend over time. Net worth's largest components (investments, home equity,
loans) never appear in transaction statements, so the source of truth is a **manual accounts
ledger**, *augmented* by auto-capturing bank-statement running balances where they exist.

This is decoupled from the transaction/category machinery: accounts are their own ledger. (A
later reconciliation wave may link accounts to transactions; not in scope here.)

## Data model

Two new tables, created in `init_db` with `CREATE TABLE IF NOT EXISTS` (no migration of existing
tables; existing data untouched).

```
accounts
  id          INTEGER PRIMARY KEY
  person_id   INTEGER NULL          -- NULL = shared/household; else FK to people.id
  name        TEXT NOT NULL         -- "BofA Checking", "Vanguard", "Home"
  kind        TEXT NOT NULL         -- checking|savings|credit_card|investment|property|loan|other
  is_asset    INTEGER NOT NULL      -- 1 = asset, 0 = liability
  balance     REAL NOT NULL DEFAULT 0   -- current balance, stored as a POSITIVE magnitude
  updated_at  TEXT NOT NULL

balance_snapshots
  id          INTEGER PRIMARY KEY
  account_id  INTEGER NOT NULL      -- FK to accounts.id (ON DELETE CASCADE in app logic)
  date        TEXT NOT NULL         -- ISO 'YYYY-MM-DD'
  balance     REAL NOT NULL         -- positive magnitude, same convention as accounts.balance
  UNIQUE(account_id, date)          -- at most one snapshot per account per day (upsert)
```

- `balance` is always a positive magnitude. Whether it adds to or subtracts from net worth is
  determined by `is_asset`, never by the sign of `balance`. This keeps liabilities intuitive
  ("I owe $4,200" → balance 4200, is_asset 0).
- `is_asset` defaults from `kind` (checking/savings/investment/property/other → asset;
  credit_card/loan → liability) but is stored explicitly so an unusual case can override it.
- Deleting an account deletes its snapshots.

## Computations (modules/analytics.py — pure, unit-tested)

**`net_worth(accounts) -> {"assets": float, "liabilities": float, "net": float}`**
- assets = Σ balance where is_asset; liabilities = Σ balance where not is_asset; net = assets − liabilities.
- Empty → all zeros.

**`net_worth_trend(snapshots) -> DataFrame[date, assets, liabilities, net]`**
- For each date that has ≥1 snapshot, each account contributes its most-recent snapshot on or
  before that date (forward-fill). An account with no snapshot on/before a date contributes 0
  (it didn't exist yet). Produces a step-series suitable for a line chart.
- Needs each snapshot tagged with its account's is_asset; the DB read joins that in.
- < 2 dates → caller shows the current number only, no trend line.

## Snapshot writes (when balance changes)

A snapshot (UNIQUE per account+day, so re-writes on the same day overwrite) is written on:
- **Account creation** with an initial balance → snapshot dated today.
- **Manual balance edit** → snapshot dated today.
- **Auto-refresh from a statement** → snapshot dated the statement's latest row date.

## Auto-refresh from bank statements

1. **Format spec** gains an optional `parse.balance_header`. `csv_formats.md` documents it; the
   *BofA Bank Statement* format sets `"balance_header": "Running Bal."`. Credit-card/Amazon
   formats omit it (no running balance), so they never offer auto-refresh.
2. **Parser** (`agent_parser._apply_spec`): when `balance_col` is present, parse each row's
   running balance (reusing the existing amount-cleaning: strip `$`, commas, parens). The
   captured value rides along but is **not** stored on the transaction.
3. **`build_preview`** returns `statement_balance = {"amount": X, "date": D}` taken from the
   latest-dated parsed row that has a balance, or `None`.
4. **Import UI**: when `statement_balance` is present, show
   *"Statement ending balance $X as of D — update an account?"* with a dropdown:
   `(don't update) | <each of this view's accounts> | + create new account`. On import, if an
   account is chosen, set its `balance = X` and write a snapshot dated `D`.
   - Explicit choice only — **no** automatic source→account matching (avoids ambiguity with
     multiple bank accounts).

## Per-view scope

Mirrors the existing person/shared convention:
- **You / Spouse** view → accounts with `person_id` = that person.
- **Household** view → all accounts (both people + shared `person_id IS NULL`).
Net worth, breakdown, and trend all respect the active view.

## UI

**Delta convention** (used by both the tab metric and the Dashboard KPI): current net =
`net_worth(live accounts)`; delta = current net − `net` at the previous date in `net_worth_trend`
(i.e. the second-to-last trend date). Since every balance change writes a same-day snapshot, the
last trend point equals current net, so the delta reads as "change since the prior snapshot
date." No delta shown when the trend has < 2 dates.

**New "Net Worth" tab** (added to the existing tab row):
- Top: net-worth number as a large metric with the delta above, plus Assets and Liabilities
  sub-metrics.
- **Trend** (Altair line of `net`) when ≥2 snapshot dates exist; otherwise a caption.
- **Accounts** management: one bordered row per account (name · kind · asset/liability ·
  balance), with an **Edit** popover (update balance, delete) — mirroring the Goals tab pattern.
  An **"➕ Add account"** expander: name, kind (selectbox), is_asset (defaulted from kind),
  balance, owner (Shared/You/Spouse).

**Dashboard**: add a **Net worth** KPI (current value + delta vs previous snapshot) alongside the
monthly Income/Spend/Savings/Savings-rate metrics.

## Testing

- **analytics** (stdlib unittest, `tests/test_networth.py`): `net_worth` assets/liabilities/net
  and empty; `net_worth_trend` forward-fill across dates, single vs multiple accounts,
  liabilities reducing net, < 2 dates.
- **DB** (integration smoke, temp DB like the existing one): accounts CRUD; snapshot upsert
  (one per account/day); per-view filtering; cascade delete.
- All existing tests must stay green; app must boot headless.

## Out of scope (YAGNI)

- Automatic source→account matching (explicit dropdown only).
- Multi-currency; investment lot tracking; editing snapshot history by hand.
- Linking accounts to individual transactions (deferred to the reconciliation wave).

## Components & boundaries

- `modules/database.py` — accounts/snapshots schema + CRUD + per-view queries + snapshot upsert.
- `modules/analytics.py` — `net_worth`, `net_worth_trend` (pure).
- `modules/formats.py` + `modules/agent_parser.py` — pass through and capture `balance_header`.
- `app.py` — Net Worth tab, Dashboard KPI, import-time auto-refresh dropdown.
- `tests/` — analytics unit tests + DB smoke.
