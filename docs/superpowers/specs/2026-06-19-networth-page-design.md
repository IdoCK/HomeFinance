# Plan 8 — Net Worth Page Design

> Page-level addendum to `2026-06-18-finance-ui-rewrite-design.md` (§4 IA, §7 API)
> and the engine design `2026-06-17-net-worth-design.md` (tables + analytics, already
> implemented). Covers the **Net Worth** React page + its backend router. No engine changes.

## Goal
Answer "are we building wealth?" — show household **net worth** (assets − liabilities) with a
trend, a per-account ledger with inline balance editing, add, and delete. Reuses the engine's
`analytics.net_worth` / `net_worth_trend` and the `accounts`/`balance_snapshots` CRUD.

## Backend contract (new — `backend/api/networth.py`, prefix `/networth`)
All delegate to existing engine functions.
- `GET /api/networth?person_id=` → one bundle:
  `{ summary: {assets, liabilities, net}, delta: number|null, accounts: Account[], trend: Point[] }`
  - `accounts` = `db.list_accounts(pid_or_all)`; each `{ id, person_id, name, kind, is_asset(0|1), balance, updated_at }`.
  - `summary` = `analytics.net_worth(accounts)`.
  - `trend` = `analytics.net_worth_trend(db.get_snapshots(pid_or_all))` → records
    `{date, assets, liabilities, net}` (empty list when no snapshots).
  - `delta` = `summary.net − trend[-2].net` when `len(trend) ≥ 2`, else `null` (change since the
    prior snapshot date, per the engine design's delta convention).
- `POST /api/networth/accounts` body `{ person_id?: int|null, name, kind, is_asset: bool, balance?: float=0 }`
  → `db.add_account(...)` (writes a snapshot dated today); returns `{ ok: true, id }`.
- `PATCH /api/networth/accounts/{id}` body `{ balance: float }` → `db.update_account_balance`
  (updates + today snapshot); returns `{ ok: true }`.
- `DELETE /api/networth/accounts/{id}` → `db.delete_account` (cascades snapshots); `{ ok: true }`.

## Persona mapping (locked, same as Goals)
`db.list_accounts`/`get_snapshots` take `int | None | "all"`. The persona sends `person_id` (int)
or omits it (Joint):
- **You / Spouse** → `person_id` int → that person's accounts.
- **Joint** → omitted → router maps to `"all"` (household: both people + shared).
- An account **added from Joint** → `person_id` null (shared); from You/Spouse → that person.

## Frontend (`web/src/pages/NetWorth.tsx`)
- **Hero**: big net number (`--testid networth-total`), the `delta` above it (green `--pos` when
  > 0, red `--neg` when < 0, hidden when null), plus Assets and Liabilities sub-metrics.
- **Trend**: a minimal inline-SVG sparkline of `trend[].net` when `trend.length ≥ 2`; otherwise a
  muted caption ("Add a second snapshot to see a trend"). No chart dependency.
- **Accounts ledger**: assets-first (engine already orders `is_asset DESC, name`). One card per
  account: name, kind badge, asset/liability tag, an inline numeric **balance** input (commit on
  blur → `updateAccountBalance`), and a ✕ delete (`aria-label="Remove {name} account"`).
- **Add form** (toggle): name, kind (select), balance; `is_asset` is **derived from kind**
  (`credit_card`/`loan` → liability, else asset); owner = the active persona (You/Spouse → that
  person, Joint → shared). Refetch after every mutation (same as Budgets/Goals).
- Frosted Ledger: `--persona` accent, `--pos`/`--neg` for asset/liability and delta, tabular
  numerals, 18px cards.

## Out of scope
Per-account snapshot history charts, statement auto-refresh (import wizard — Plan for Import),
editing snapshot history, explicit `is_asset` override in the add form (derived from kind only),
linking accounts to transactions. (Future.)
