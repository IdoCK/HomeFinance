# Finance Overhaul — Implementation Plan (Agent-Review Findings)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. UI tasks additionally REQUIRE frontend-design:frontend-design. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix every correctness, clarity, and completeness finding raised by the four specialist advisors (accounting, growth, home-finance, dashboard-graphs) and build the missing dashboard features, so HomeFinance honestly answers "are we okay this month?" and "are we building wealth?"

**Architecture:** FastAPI backend (`backend/api/*.py`) over a pure-Python engine (`modules/*.py`); Vite + React 19 + TypeScript SPA (`web/src/`) with bespoke SVG chart primitives (the "Frosted Ledger" identity) and shadcn/ui (radix-nova) components. Backend changes are TDD against `tests/` (pytest). Frontend changes are TDD against vitest + Testing Library, and every visual task runs through the frontend-design skill.

**Tech Stack:** Python 3 / FastAPI / pandas / sqlite; React 19 / Vite / Tailwind 4 / shadcn-ui (radix-nova) / TanStack Table / lucide-react / sonner / vitest.

## Global Constraints

- **USD is the canonical pivot.** Every analytics computation runs on `amount_base` (USD) via `fx.base_txns(...)`; display conversion is the LAST step via `fx.display_factor(display)`. The same figure must read identically on every page. (`modules/fx.py`)
- **Data minimization is invariant.** The only outbound network call is `fx.fetch_rate` (date + currency pair only). No new telemetry, no amounts leaving the machine except the existing anonymized AI-insights path.
- **Persona identity:** Ido = blue (`--persona-solid`/`--persona-ido`), Aviv = pink (`--persona-spouse`), Joint = gradient (`--persona-joint-solid`). Never encode persona by color alone — always pair with a label/shape/position.
- **Honesty over decoration:** charts must carry a readable scale (zero baseline + min/max), never hide sign, and visually distinguish in-progress (partial) months from complete ones. The engine already computes `complete`; the UI must show it.
- **Prefer prebuilt components:** use shadcn/ui primitives (`badge`, `alert`, `progress`, `tabs`, `tooltip`, `card`, `separator`, `skeleton`) for new UI surfaces; extend the bespoke SVG primitives in `web/src/components/charts/` rather than introducing a charting library (preserves the Frosted Ledger identity and zero bundle cost).
- **Tests:** backend `venv/Scripts/python.exe -m pytest tests/ -q`; frontend `cd web && npm test`. Every task ends green. Atomic commit per task.
- **Money rendering:** all currency goes through `<Money>` (`web/src/components/money.tsx`); statement/reconcile figures render in the STATEMENT's own currency, not the global display toggle.

---

## Wave map (dependency order)

| Wave | Theme | Lens | Depends on |
|---|---|---|---|
| **1** | Books correctness (numbers must be true first) | accounting | — |
| **2** | Chart primitives & honesty (axes, signs, partial-month, a11y) | dashboard | — |
| **3** | Present-month features ("are we okay this month?") | home-finance | 1, 2 |
| **4** | Wealth features ("are we building wealth?") | growth | 1, 2 |
| **5** | Declutter / REMOVE (de-dupe, kill vanity metrics) | all | 1–4 |
| **6** | Verification, a11y audit, visual polish, docs/memory | all | 1–5 |

Waves 1 and 2 are independent of each other and can run in parallel. Waves 3 and 4 both consume 1 + 2. Wave 5 cleans up after the new surfaces exist. Wave 6 is the final gate.

---

# WAVE 1 — Books correctness (backend, TDD)

The dependency root: every page renders engine numbers, so these must be correct before any UI work. Reference pattern for currency handling is `backend/api/overview.py:26` (`fx.base_txns` → analytics → `display_factor`).

### Task 1.1: Make Analysis & Insights currency-consistent (CRITICAL)

**Files:**
- Modify: `backend/api/analysis.py` (endpoints `category_trend`, `drill`, `compare`, `overlap` — each opens with raw `db.get_transactions(...)`)
- Modify: `backend/api/insights.py` (`_summaries`, lines 19-34)
- Test: `tests/test_analysis_currency.py` (create)

**Interfaces:**
- Consumes: `fx.base_txns(txns) -> list[dict]` (sets `amount` to USD `amount_base`); `fx.display_factor(display) -> float | None`.
- Produces: every Analysis endpoint gains a `display: str = "USD"` query param and returns money already scaled to display currency, identical in scale to Overview/Budgets.

- [ ] **Step 1 — Write the failing test.** With a mixed-currency fixture (one USD row, one ILS row whose `amount_base` differs from `amount`), assert that `/analysis/category-trend` totals equal the Overview's `category_totals` for the same window (i.e. computed from `amount_base`, not raw `amount`). Assert `/analysis/drill` and `/analysis/compare` likewise sum base amounts.
- [ ] **Step 2 — Run it; confirm it FAILS** (current code sums raw `amount`).
- [ ] **Step 3 — Implement:** in each of the four `analysis.py` endpoints replace `txns = db.get_transactions(person_id)` with `txns = fx.base_txns(db.get_transactions(person_id))`; add `display: str = "USD"` param and a `f = fx.display_factor(display) or 1.0`; scale the money fields of each response (`values`, `total`, `value`, `amount`, bucket `total`/`per_day`, category `a`/`b`, `spend`) by `f` at the end (mirror `overview._scale`). In `insights._summaries`, wrap each `db.get_transactions(...)` in `fx.base_txns(...)`.
- [ ] **Step 4 — Update the frontend callers** in `web/src/lib/api.ts` (`getCategoryTrend`, `getDrill`, `getCompare`, `getOverlap`) to forward `display`, and the Analysis page/components to pass the active currency.
- [ ] **Step 5 — Run backend + frontend tests; confirm PASS.**
- [ ] **Step 6 — Commit:** `fix(analysis): run analytics on USD base + scale to display currency (was summing mixed currencies)`

### Task 1.2: Reconcile per-statement, in the statement's own currency (HIGH)

**Files:**
- Modify: `modules/analytics.py` (`reconcile`) — accept/return a `currency`
- Modify: `backend/api/networth.py` (reconcile endpoint, ~line 75) — group by `(person, file_hash)` instead of pooling the household
- Modify: `web/src/lib/api.ts` (`Reconciliation` type → list of per-statement results, add `currency`, `filename`), `web/src/pages/NetWorth.tsx` (render one card per statement, format figures in `recon.currency`, not the global toggle)
- Test: `tests/test_reconcile_scope.py` (create)

**Interfaces:**
- Produces: `GET /networth/reconcile` returns `{ statements: [{ filename, currency, begin, end, computed_end, discrepancy, n, chain_breaks, ok }] }`.

- [ ] **Step 1 — Failing test:** two statements (different accounts/currencies) for the same person reconcile INDEPENDENTLY; a single pooled chain is never computed; each result carries its statement `currency`.
- [ ] **Step 2 — Confirm FAIL** (current code pools `db.get_transactions(person_id)` into one chain).
- [ ] **Step 3 — Implement** per-statement grouping (`db.transactions_for_file` / `file_hash`); return raw statement-currency values untouched; include `currency`.
- [ ] **Step 4 — Frontend:** render a reconcile card per statement; format with the statement currency (a fixed `<Money currency={recon.currency}>`), independent of the display toggle. (Pairs with REMOVE Task 5.4 which drops the old pooled card.)
- [ ] **Step 5 — Tests PASS.**
- [ ] **Step 6 — Commit:** `fix(reconcile): per-statement scope + statement-currency formatting`

### Task 1.3: Currency-aware transfer matching (HIGH)

**Files:**
- Modify: `modules/analytics.py` (`find_transfer_pairs`, ~line 206-275) — match on `amount_base` within tolerance OR require `out.currency == in.currency`
- Modify: `backend/api/transactions.py` (transfer endpoint, ~line 35) — feed `fx.base_txns(...)` and surface each leg's currency
- Modify: `web/src/pages/Transactions.tsx` (transfer-pair card ~line 213-230) — show the pair amount in its real currency
- Test: `tests/test_transfer_currency.py` (create)

- [ ] **Step 1 — Failing test:** a ₪370 outflow and a $370 inflow must NOT pair; a $370/$370 pair (or two legs equal in base) still pairs.
- [ ] **Step 2 — Confirm FAIL** (current key is `round(abs(amount),2)` on raw amount).
- [ ] **Step 3 — Implement:** key on `amount_base` within a small tolerance, and/or guard `out.currency == in.currency`.
- [ ] **Step 4 — Frontend** currency badge on the leg.
- [ ] **Step 5 — Tests PASS.**
- [ ] **Step 6 — Commit:** `fix(transfers): currency-aware pair matching`

### Task 1.4: Convert budget caps from their stored currency (MED)

**Files:**
- Modify: `backend/api/budgets.py` (~line 16-24) — convert each budget's `amount` from its stored `currency` to USD via `fx.to_base` BEFORE `analytics.budget_status`, then scale to display
- Test: `tests/test_budget_currency.py` (create)

- [ ] **Step 1 — Failing test:** a budget stored as ₪1000 with USD spend is paced against the USD-converted cap (~$270), not against $1000.
- [ ] **Step 2 — Confirm FAIL.**
- [ ] **Step 3 — Implement** the per-budget `to_base` conversion.
- [ ] **Step 4 — Tests PASS.**
- [ ] **Step 5 — Commit:** `fix(budgets): convert budget cap from stored currency to USD base`

### Task 1.5: Goal pace status + deadline-overdue fix (MED) — engine half

**Files:**
- Modify: `modules/analytics.py` (`goal_progress`, ~line 430-446)
- Modify: `backend/api/goals.py` (pass household `avg_monthly_savings`; expose new fields)
- Modify: `web/src/lib/api.ts` (`Goal` type: add `status`, `projected_completion`)
- Test: `tests/test_goal_progress.py` (create/extend)

**Interfaces:**
- Produces: `goal_progress(...)` returns per goal `status: "ahead" | "on_track" | "behind" | "overdue"` and `projected_completion: str | None`. The UI half (badges) is Wave 4 Task 4.3.

- [ ] **Step 1 — Failing test (a):** a goal whose `target_date` is this month/past and is unmet returns `status="overdue"` (NOT `monthly_needed = remaining` silently). **(b):** given actual avg monthly savings below `monthly_needed`, status is `behind`; above, `ahead`; near, `on_track`. **(c):** `projected_completion = today + remaining / actual_monthly_savings`.
- [ ] **Step 2 — Confirm FAIL.**
- [ ] **Step 3 — Implement:** accept `actual_monthly_savings`; fix the `months_left == 0` branch to return `overdue`; compute `status` + `projected_completion`. Source `avg_monthly_savings` in `goals.py` from `analytics.monthly_savings`/`cash_flow` on `fx.base_txns`.
- [ ] **Step 4 — Tests PASS.**
- [ ] **Step 5 — Commit:** `feat(goals): pace status + projected completion; fix overdue deadline handling`

### Task 1.6: Uncategorized-spend surface (MED) — engine/endpoint half

**Files:**
- Modify: `backend/api/overview.py` — add `uncategorized: { count: int, amount: float }` to the response (amount scaled to display)
- Modify: `web/src/lib/api.ts` (`Overview` type)
- Test: `tests/test_overview_uncategorized.py` (create)

- [ ] **Step 1 — Failing test:** overview reports the count and base-summed amount of rows whose category is empty/`Uncategorized` for the selected month.
- [ ] **Step 2 — Confirm FAIL.**
- [ ] **Step 3 — Implement** the aggregate (reuse `db.get_uncategorized_descriptions` / category filter).
- [ ] **Step 4 — Tests PASS.**
- [ ] **Step 5 — Commit:** `feat(overview): expose uncategorized count/amount` (UI badge is Wave 3 Task 3.6).

### Task 1.7: Untracked legacy-rows surface (MED)

**Files:**
- Modify: `backend/api/imports.py` (or a small `/transactions/untracked-count`) — expose `count_untracked_transactions`
- Modify: `web/src/lib/api.ts`; UI lands on Settings/Import in Wave 5
- Test: `tests/test_untracked_count.py` (create)

- [ ] **Step 1 — Failing test:** endpoint returns the count of `file_hash IS NULL` rows.
- [ ] **Step 2 — Confirm FAIL.**
- [ ] **Step 3 — Implement** (reuse `database.count_untracked_transactions`).
- [ ] **Step 4 — Tests PASS.**
- [ ] **Step 5 — Commit:** `feat(imports): expose untracked-row count`

### Task 1.8: FX freshness hygiene (LOW)

**Files:**
- Modify: `backend/api/fx.py` (`/fx/refresh` chains `recompute_amount_base`); `modules/money` surface used by `web/src/components/money.tsx` to show rate age when nearest-prior fallback fired
- Modify: `modules/fx.py` (`get_rate` / a thin wrapper) to optionally report the age of the rate used
- Test: `tests/test_fx_freshness.py` (create)

- [ ] **Step 1 — Failing test:** after `/fx/refresh`, stale `amount_base` rows are recomputed; a rate older than the txn date by > N days is reported with its age.
- [ ] **Step 2 — Confirm FAIL.**
- [ ] **Step 3 — Implement** the chain + age reporting (no new network behavior).
- [ ] **Step 4 — Tests PASS.**
- [ ] **Step 5 — Commit:** `feat(fx): recompute on refresh + surface rate age`

**Wave 1 gate:** full pytest suite green; manual check that a seeded ILS row shows the same category total on Overview and Analysis.

---

# WAVE 2 — Chart primitives & honesty (frontend, TDD + frontend-design)

Extend the bespoke SVG primitives in `web/src/components/charts/`. Run frontend-design for the visual language of axes/labels/partial-month hatching. Every task: vitest test + visual check.

### Task 2.1: Signed BarChart with zero baseline (HIGH)

**Files:** Modify `web/src/components/charts/bar-chart.tsx`; Test `web/src/components/charts/bar-chart.test.tsx` (create).
- Replace `Math.abs(d.value)` height logic (lines 16, 22) with a signed domain: bars grow up for positive, down from a zero baseline for negative; negative bars use `var(--neg)`/`--fl-neg`, positive use the persona/positive color. Add the zero line.
- [ ] Failing test: a `-30` datum renders below the baseline with the negative color; `+30` renders above with equal magnitude. → confirm FAIL → implement → PASS → commit `fix(charts): BarChart honors sign with a zero baseline`.

### Task 2.2: Y-axis scale + value labels on AreaChart & LineChart (HIGH)

**Files:** Modify `web/src/components/charts/area-chart.tsx`, `line-chart.tsx`, `_svg.ts` (add an `axisTicks(min,max)` helper); add optional `showAxis`, `valueFormat` props. Tests in `*.test.tsx`.
- Render min/max/zero y labels (and faint gridlines), plus the current/last point value. Domain comes from the existing honest `layout`/`layoutShared` (already includes 0).
- Fix `preserveAspectRatio="none"` distortion (render at a measured width, or letterbox) so trend slope is truthful.
- [ ] Failing tests (axis labels present; zero gridline present; value label shows) → FAIL → implement → PASS → commit `feat(charts): readable y-axis, gridlines and value labels`.

### Task 2.3: Partial-month visual marker (HIGH)

**Files:** Modify `area-chart.tsx`, `line-chart.tsx`, `bar-chart.tsx` to accept a `partialFromIndex`/`partial?: boolean[]` prop; the final in-progress segment/bar renders dashed/hatched with a "(so far)" affordance. Helper in `_svg.ts`. Tests in `*.test.tsx`.
- [ ] Failing test: when the last point is partial, its segment is dashed/hatched and labeled → FAIL → implement → PASS → commit `feat(charts): mark in-progress (partial) months distinctly`.

### Task 2.4: Accessibility & persona-color correctness (MED)

**Files:** Modify `web/src/components/charts/diverging-bar-chart.tsx`, `dot-matrix.tsx`, `web/src/lib/persona.tsx` (`personColor` Joint → gradient/`--persona-joint-solid`, not blue), `_svg.ts` (drop `#3B82F6`/`#EC4899` persona hues from the generic `CATEGORY_COLORS` ramp).
- Add a non-color cue to persona encodings (label/shape/position; diverging already separates by side — add a name label to the dot-matrix). Tests in `*.test.tsx`.
- [ ] Failing tests (Joint resolves to gradient; dot-matrix has a text label; CATEGORY_COLORS excludes persona hues) → FAIL → implement → PASS → commit `fix(charts): colorblind-safe persona encoding + correct Joint color`.

### Task 2.5: Extract Sparkline + shared Legend/Axis primitives (LOW)

**Files:** Create `web/src/components/charts/sparkline.tsx` (named wrapper over the line path, ≥2-pt gate), `legend.tsx` (one swatch shape); refactor NetWorth per-account sparkline + LineChart/Diverging/Grouped legends to use them. Tests.
- [ ] Failing test (Sparkline renders ≥2 pts, refuses <2) → FAIL → implement → PASS → commit `refactor(charts): shared Sparkline + Legend primitives`.

**Wave 2 gate:** `cd web && npm test` green; frontend-design visual review of the new axis/partial-month language.

---

# WAVE 3 — Present-month features (home-finance lens)

Consumes Wave 1 numbers + Wave 2 primitives. Use frontend-design + shadcn (`alert`, `badge`, `progress`, `card`).

### Task 3.1: Partial-month banner + safe MoM delta (HIGH)
**Files:** `web/src/pages/Overview.tsx` (use the already-fetched `data.complete` / `series[].complete`); guard the delta at lines ~81-82 to only show ▲/▼ when both months are `complete`, else label "(partial)".
- shadcn `alert` (subtle) "June — in progress (12 of 30 days)" when `!complete`. Test in `Overview.test.tsx`.
- [ ] Failing test → FAIL → implement → PASS → commit `feat(overview): surface partial-month state; guard MoM delta`.

### Task 3.2: "Safe to spend / left this month" hero (HIGH)
**Files:** Backend `backend/api/overview.py` — add `safe_to_spend` = income − committed (from `analytics.committed_monthly`) − discretionary-budgeted-so-far (scaled to display). `web/src/lib/api.ts` type; new hero card on `Overview.tsx` (shadcn `card` + `<Money>`). Tests both sides.
- [ ] Failing tests (backend value; card renders) → FAIL → implement → PASS → commit `feat(overview): safe-to-spend hero`.

### Task 3.3: Committed vs discretionary split (MED)
**Files:** `Overview.tsx` "This month" spend bar (~lines 73-78) split into committed (`committed_monthly`) vs discretionary, via `StackedBars`. Test.
- [ ] Failing test → FAIL → implement → PASS → commit `feat(overview): committed vs discretionary spend split`.

### Task 3.4: Bills still due this month (MED)
**Files:** Backend aggregate of `recurring_charges` whose `next_expected` falls in the remaining days → `{ count, amount }`; surface a summary line on `Overview.tsx` and a section on `Recurring.tsx`. Tests.
- [ ] Failing tests → FAIL → implement → PASS → commit `feat(recurring): bills-due-this-month summary`.

### Task 3.5: Budgets household roll-up hero (MED)
**Files:** Backend `backend/api/budgets.py` add a summary (total budgeted, total spent, unbudgeted spend this month, all base→display); `web/src/pages/Budgets.tsx` hero above the rows (shadcn `card` + Wave 2 `PaceMeter`). Tests.
- [ ] Failing tests → FAIL → implement → PASS → commit `feat(budgets): household roll-up with unbudgeted-spend`.

### Task 3.6: Promote the "are we okay" verdict + uncategorized badge (MED)
**Files:** `Overview.tsx` — move the muted footnote verdict (~lines 143-146) to a prominent color+icon+text status line (shadcn `badge`/`alert`); add an "$X across N uncategorized" badge (from Wave 1 Task 1.6) linking to a filtered Transactions view. Test.
- [ ] Failing test → FAIL → implement → PASS → commit `feat(overview): prominent monthly verdict + uncategorized badge`.

**Wave 3 gate:** frontend + backend tests green; frontend-design review of Overview hierarchy.

---

# WAVE 4 — Wealth features (growth lens)

Consumes Wave 1 (goal status) + Wave 2 (axis/sparkline). frontend-design + shadcn.

### Task 4.1: Net-worth trend rebuild (HIGH)
**Files:** `web/src/pages/NetWorth.tsx` (~line 208) — replace the context-free 64px sparkline with a dated, labeled trend using the full `trend` payload (assets/liabilities/date) and Wave 2 axis; overlay round-number milestone markers ($100k/$250k/$500k/$1M). Test.
- [ ] Failing test (dates + milestone markers render) → FAIL → implement → PASS → commit `feat(networth): dated net-worth trend with milestones`.

### Task 4.2: Savings-rate trajectory with benchmark band (HIGH)
**Files:** `Overview.tsx` savings-rate card — rolling 3-month average over `series[].savings_rate` + horizontal reference lines at 20% (advisor) and 50% (FIRE) + one-line verdict. Uses signed BarChart/LineChart from Wave 2. Test.
- [ ] Failing test → FAIL → implement → PASS → commit `feat(overview): savings-rate trajectory + benchmark band`.

### Task 4.3: Goal pace badges + projected completion (HIGH)
**Files:** `web/src/pages/Goals.tsx` — render `status` (ahead/on-track/behind/overdue) as a shadcn `badge` + projected-completion date (from Wave 1 Task 1.5). Test.
- [ ] Failing test → FAIL → implement → PASS → commit `feat(goals): pace badges + projected completion date`.

### Task 4.4: Net-worth projection (MED)
**Files:** Backend `backend/api/networth.py` — `projection` = linear (avg monthly savings) + compounding curve at a user-editable assumed annual return (default 7% nominal, marked an assumption); `Settings.tsx` exposes the rate; `NetWorth.tsx` overlays the projection on the trend. Tests.
- [ ] Failing tests → FAIL → implement → PASS → commit `feat(networth): net-worth projection (linear + compounding)`.

### Task 4.5: Contributions-vs-net-worth overlay (MED)
**Files:** `Overview.tsx` Trend view — plot cumulative contributions (existing `:59` logic) against the net-worth trend on one axis; the gap visualizes returns/appreciation. Test.
- [ ] Failing test → FAIL → implement → PASS → commit `feat(overview): contributions vs net-worth overlay`.

### Task 4.6: FIRE runway, 25× target, trailing-12m growth + CAGR (LOW)
**Files:** Backend net-worth growth helper (trailing-12m $ and %, CAGR over snapshot span) + FIRE number (25× annual expenses) and runway (net worth ÷ `committed_monthly`); surface as stats on `NetWorth.tsx`. Tests.
- [ ] Failing tests → FAIL → implement → PASS → commit `feat(networth): growth/CAGR stats + FIRE runway`.

### Task 4.7: Per-horizon goal compounding + snapshot FX decision (LOW)
**Files:** `modules/analytics.py` `goal_progress` — for `horizon=="long"` use future-value annuity math instead of flat division. Document the historical-FX-at-snapshot decision (store as-of rate vs reprice at today) in this plan's decisions log; implement only if approved. Tests for the compounding path.
- [ ] Failing test → FAIL → implement → PASS → commit `feat(goals): compounding required-contribution for long-horizon goals`.

**Wave 4 gate:** tests green; frontend-design review of NetWorth + Goals.

---

# WAVE 5 — Declutter / REMOVE

### Task 5.1: Overview AI-Insights card — drop duplicated net headline
`Overview.tsx:185-186` — replace `headline={<Money value={data.net} />}` with a genuine insight teaser (e.g. first alert / safe-to-spend), not a third copy of net. Test. Commit `refactor(overview): AI card shows an insight, not a duplicate net`.

### Task 5.2: De-dupe the net number
`Overview.tsx` — keep ONE hero net (the "This month" card); remove the redundant repetition across the Net KPI / AI card so net appears once prominently. Test. Commit `refactor(overview): single hero net`.

### Task 5.3: De-dupe multi-month trend
Let Overview own *this month*; let Analysis own *trends*. Remove/redirect the overlapping "Trend" duplication (`Overview.tsx` Trend mode vs `Analysis` category-over-time) per the agreed split. Test. Commit `refactor: Overview=this-month, Analysis=trends (de-dupe)`.

### Task 5.4: Remove the pooled Joint reconcile card
`NetWorth.tsx:230-248` — delete the old cross-statement pooled card (superseded by per-statement cards from Task 1.2). Test. Commit `refactor(networth): drop pooled reconcile card`.

### Task 5.5: Recurring confidence → filter, not display
`Recurring.tsx:36-38` — stop rendering the model-internal confidence bar; use confidence only to filter/sort. Test. Commit `refactor(recurring): hide internal confidence metric`.

### Task 5.6: Top-categories dot-matrix → Joint-only / ranked bar
`Overview.tsx:177-181` — keep the dot-matrix for the Joint who-spent-what split only; in single-persona view show a compact ranked bar instead (avoids duplicating Analysis drill-down). Test. Commit `refactor(overview): right chart per persona view`.

### Task 5.7: Untracked-rows + uncategorized actions land in Settings/Import
Surface Task 1.7 untracked count (with the existing clear action) on Settings/Import. Test. Commit `feat(settings): untracked-row audit banner`.

---

# WAVE 6 — Verification, a11y, polish, docs

- [ ] Full backend suite: `venv/Scripts/python.exe -m pytest tests/ -q` — all green.
- [ ] Full frontend suite: `cd web && npm test` — all green; `npm run build` clean (tsc).
- [ ] Run the **verify** / **run** skill: boot the app, click through every page, confirm the same figure reads identically across Overview/Analysis/Budgets with a seeded ILS row.
- [ ] frontend-design pass on Overview, NetWorth, Budgets, Goals for hierarchy/identity consistency; colorblind check (simulate) on persona encodings.
- [ ] Update memory: refresh `finance-overhaul-backlog.md` (it predates the React rewrite); add a memory noting the multi-currency consistency invariant and the partial-month honesty rule.
- [ ] Final commit / PR: `feat: finance overhaul — correctness, charts, present-month & wealth features`.

---

## Self-review coverage map (every agent finding → task)

- Multi-currency Analysis/Insights divergence (CRITICAL) → **1.1**
- Reconcile wrong currency + Joint pooling (HIGH) → **1.2** + **5.4**
- Transfer matching currency-blind (HIGH) → **1.3**
- Budget cap not converted (MED) → **1.4**
- Goal `months_left==0` overdue bug + no pace status (MED/HIGH) → **1.5** + **4.3**
- Uncategorized leakage unsurfaced (MED) → **1.6** + **3.6**
- Untracked legacy rows (MED) → **1.7** + **5.7**
- FX nearest-prior staleness / recompute-on-refresh (LOW) → **1.8**
- BarChart erases sign (HIGH) → **2.1**
- No y-axis/labels on area & line; aspect distortion (HIGH) → **2.2**
- `complete` flag fetched but never shown (HIGH, all lenses) → **2.3** + **3.1**
- Color-only persona / Joint→blue / persona hues in ramp (MED, a11y/EAA) → **2.4**
- Sparkline/Legend duplication (LOW) → **2.5**
- Partial-month banner + unsafe MoM delta (HIGH) → **3.1**
- No safe-to-spend (HIGH) → **3.2**
- Committed vs discretionary disconnected (MED) → **3.3**
- Bills-due-this-month missing (MED) → **3.4**
- Budget totals + unbudgeted spend missing (MED) → **3.5**
- "Are we okay" verdict buried (MED) → **3.6**
- NetWorth context-free sparkline (HIGH) → **4.1**
- Savings rate not a trajectory / no benchmark (HIGH) → **4.2**
- No projection/compounding (MED) → **4.4** + **4.7**
- Contributions vs net-worth (MED) → **4.5**
- FIRE runway / CAGR (LOW) → **4.6**
- Overview AI card duplicates net; net repeated 3× (High/Med) → **5.1** + **5.2**
- Duplicated trend view (Med) → **5.3**
- Recurring confidence vanity (Low) → **5.5**
- Top-categories dot-matrix duplication (Med) → **5.6**

## Open decisions (resolve at execution)
1. **Historical FX at snapshot** (Task 4.7): store the as-of rate on each balance snapshot vs reprice the whole trend at today's rate. Repricing distorts the ₪ partner's trajectory; storing as-of is correct but a schema add. Default recommendation: store as-of rate going forward, leave existing snapshots repriced with a caveat.
2. **Assumed return rate default** (Task 4.4): 7% nominal as a user-editable assumption; surfaced in Settings.
