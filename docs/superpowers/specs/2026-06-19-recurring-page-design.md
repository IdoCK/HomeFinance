# Plan 6 — Recurring Page Design

> Page-level addendum to `2026-06-18-finance-ui-rewrite-design.md` (§4 IA, §7 API).
> Covers the **Recurring** page + its backend router. Net Worth is a separate later
> plan (Plan 7). Locked decisions below.

## Goal
Surface detected subscriptions & regular bills: the committed monthly spend, each
recurring charge with its cadence / cost / next date, and anomaly flags (price changes,
new, possibly-canceled). **Read-only** — recurring is derived by the engine, not stored.

## Backend contract (new — `backend/api/recurring.py`)
Thin; delegates to the engine; no engine changes.
- `GET /api/recurring?person_id=` →
  `{ charges: RecurringCharge[], committed: {fixed, variable, total}, anomalies: Anomaly[] }`
  via `analytics.recurring_charges(txns, vendor_rules)` + `committed_monthly` +
  `recurring_anomalies`.
- **Vendor rules (LOCKED — user chose to use them):** for a real person, fetch
  `db.get_vendors(person_id)` and transform each `{name, keywords}` (comma-separated
  string) into `(name, [kw, …])` tuples — the shape `analytics.vendor_of` expects — so
  merchant variants (Amazon.com / AMZN MKTP → "Amazon") collapse and detect as one. For
  Joint (`person_id=None`) pass `None` (vendors are per-person).
- **Persona = natural model:** You→people[0], Spouse→people[1], **Joint→merge everyone**
  (`get_transactions(None)`), like Transactions. No household special case (unlike Budgets).
- `RecurringCharge` keys (from `recurring_charges`): `vendor, category, cadence
  (weekly|monthly|quarterly|yearly), kind (fixed|variable), typical_amount, prior_typical,
  prior_stable, first_date, last_date, last_amount, next_expected, count, monthly_cost,
  annual_cost, confidence`. `Anomaly`: `{vendor, type (price_change|possibly_canceled|new),
  detail, pct?/overdue_days?/age_days?}`.
- Register in `backend/main.py`. No request-body schema (GET-only).

## Frontend (`pages/Recurring.tsx`)
`lib/api.ts` gains `RecurringCharge` / `RecurringAnomaly` / `Committed` / `RecurringData`
types + `getRecurring({personId})`. The page is read-only (no mutations).

### Visual (Frosted Ledger — frontend-design at build)
Signature = the **committed-monthly hero with its annual shadow**: a big bold "$X/mo"
with a muted "· $Y/yr" beneath — the annual figure is the real shock of subscriptions.
Below: anomaly chips (price-change amber `#F59E0B`, possibly-canceled muted, new
persona-accent), then one card per charge — vendor, a cadence badge, a fixed/variable
tag, monthly cost prominent with annual muted, next-charge date + count, and a faint
confidence bar in the persona accent. Empty state explains the ≥3-charge threshold.
Distinct from Plan 4's ownership braid and Plan 5's pace tick.

## Out of scope (later plans)
Managing/snoozing subscriptions, vendor-rule editing (Settings plan), per-vendor cost
history charts, Net Worth (Plan 7).

## Files
- `backend/api/recurring.py` (create), `backend/main.py` (register).
- `tests/api/test_recurring.py` (create).
- `web/src/lib/api.ts` (+types & `getRecurring`), `web/src/lib/api.test.ts` (+test).
- `web/src/pages/Recurring.tsx` (create) + `web/src/pages/Recurring.test.tsx` (create).
- `web/src/routes.tsx` (swap `/recurring` placeholder).

## Testing (TDD)
- **Backend** (`tests/api/test_recurring.py`, temp-DB fixtures, dates off `date.today()`
  for determinism):
  1. seed 4 monthly "NETFLIX.COM" charges → a monthly/fixed charge is detected and
     `committed.total > 0`.
  2. add a vendor rule `Amazon: amazon,amzn`, seed 4 monthly charges across two Amazon
     description variants → they collapse to a single `vendor == "Amazon"` with `count == 4`
     (proves the vendor-rule transform).
- **Frontend** (Vitest): renders detected vendors; shows the committed total; surfaces a
  price-change anomaly chip.
- Existing engine tests for the recurring functions stay untouched.

## Commits (≈4)
1. `feat(api): recurring router (charges + committed + anomalies)`
2. `feat(web): recurring API client`
3. `feat(web): Recurring page (committed hero + charge list + anomalies)`
4. `feat(web): wire /recurring route`
