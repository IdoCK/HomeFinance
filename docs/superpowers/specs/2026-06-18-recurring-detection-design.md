# Recurring / Subscription Detection — Design (2026-06-18)

## Goal
Surface recurring charges in the two-person finance dashboard to deliver three things at once:
1. **Find forgotten subscriptions** — a clean list of recurring charges with monthly + annualized cost.
2. **Forecast committed spend** — sum known recurring obligations into a "committed monthly spend" figure (fixed vs variable).
3. **Detect anomalies** — flag price changes, likely cancellations, and newly-appeared subscriptions.

## Architecture
All detection logic is **pure** and lives in `modules/analytics.py`, consistent with the rest of the engine. **No new DB tables, no migration** — detection re-runs each render over the transaction list. Everything routes through `_df` (drops `included=0`) and `_split` (refund-netting), and groups merchants via `vendor_of(description, vendor_rules)` so variants (AMAZON MKTPL → Amazon) collapse to one subscription.

## Detection algorithm

### `recurring_charges(txns, vendor_rules=None, as_of=None) -> list[dict]`
1. Build spend rows via `_df`/`_split`; keep rows with positive `spend` (real outflows, refunds netted out — a vendor that nets to zero is not a live subscription).
2. Group by `vendor_of(description, vendor_rules)`.
3. For each vendor with **≥3 charges**, sort by date; compute consecutive gaps in days.
4. **Cadence:** median gap snapped to the nearest known period — weekly (7), monthly (~30.4), quarterly (~91), yearly (365) — within tolerance (±25% of the period; yearly looser, ±20% absolute is too tight so use proportional). Irregular gaps (high relative variance, e.g. coefficient of variation of gaps > ~0.4) → not recurring → skip.
5. **Amount class:** coefficient of variation (CV) of per-charge amounts. `CV ≤ 0.10` → `fixed`; otherwise → `variable` (usage-based bills like phone/electric still surface, flagged variable).
6. **Confidence (0–1):** blend of gap-regularity (1 − normalized gap CV), occurrence count (more charges → higher, capped), and amount tightness (fixed → higher). Used to sort and to let the UI hide low-confidence noise.
7. Per match return:
   `vendor, category, cadence ('weekly'|'monthly'|'quarterly'|'yearly'), kind ('fixed'|'variable'), typical_amount (median), last_date, last_amount, next_expected (last_date + median gap, ISO date), count, monthly_cost (typical normalized to per-month by cadence), annual_cost, confidence`.

`category` is the most common category among the vendor's charges.

### `committed_monthly(recurring) -> {'fixed', 'variable', 'total'}`
Sums `monthly_cost` across matches, split by `kind`. Powers the Dashboard card.

### `recurring_anomalies(recurring, as_of=None) -> list[dict]`
Derives flags from each match's own returned fields; no persistence:
- **price_change** — `last_amount` deviates from `typical_amount` by > 15% (only meaningful for `fixed`; skip `variable`). Reports old/new/pct.
- **possibly_canceled** — `next_expected` is more than 1.5× the cadence period in the past relative to `as_of`, with no newer charge.
- **new** — the subscription's first charge is within ~2.5 cadence periods of `as_of` (newly appeared). The headroom over 2× matters because a just-detected sub already has ≥3 charges spanning ~2 periods. (Requires first-charge date — `recurring_charges` returns `first_date`.)

Each anomaly: `{vendor, type, detail, ...}` sorted by severity/recency.

## UI

### Dashboard (`app.py`)
A compact card/KPI: **"Committed monthly spend"** showing total with a fixed-vs-variable breakdown, plus a small "⚠️ N recurring alerts" line when anomalies exist (links the user to the Analysis section mentally — no deep-link needed). Scoped by the active You/Spouse/Household view using existing `transactions_for_view` and `_view_vendor_rules(view)`.

### Analysis tab (`app.py`)
A new **Recurring** section:
- Sortable table: vendor, category, cadence, typical amount, monthly, annualized, next charge, confidence.
- A confidence slider/filter to hide low-confidence noise (default threshold ~0.5).
- Fixed vs variable grouping (or a `kind` column).
- An **Anomalies** subsection listing flagged price changes, likely cancellations, and new subscriptions.

## Testing
`tests/test_recurring.py` with synthetic fixtures:
- Clean monthly subscription (≥3 charges) → matches, `fixed`, monthly cadence, high confidence.
- Weekly and yearly subscriptions → correct cadence + normalized monthly cost.
- Variable bill (regular cadence, varying amount) → matches as `variable`.
- Irregular merchant (groceries/restaurants at random intervals) → does NOT match.
- Fewer than 3 charges → does NOT match.
- Refund / `included=0` handling → excluded rows ignored; a vendor netting to ~zero not flagged.
- Each anomaly type: price hike, canceled (overdue next_expected), new (recent first charge).
- `committed_monthly` totals and fixed/variable split.

Verification loop: `py_compile` → `pytest -q` → AppTest boot (You + Household).

## Decisions / non-goals
- **Pure-computed, no user overrides in v1** — no "mark as not-a-subscription" or alert dismissal. Keeps surface area small and matches the engine philosophy; can add an overrides table later if needed.
- Per-day/cadence normalization uses median amount, not mean, to resist outliers.
- Detection scoped per active view (person/household), like every other tab.
