# UI Rewrite — Feature Parity Gap Analysis & Reincorporation Plan

**Branch:** `ui-feature-parity` (off `ui-fix`)
**Date:** 2026-06-22
**Scope:** Identify features/charts present in the old Streamlit UI (`app.py` + `modules/`) that were dropped by the React/Vite rewrite (`web/` + `backend/`), and plan their reincorporation.

> **Status — COMPLETE (2026-06-22).** All phases shipped. Analysis surface
> restored (Explore trend + drill-down, Compare, People), shared filter bar with
> days-of-week, Overview cash-flow trend overlays (income/spend + cumulative),
> per-account NetWorth sparklines, statement-driven & manual month-end balances,
> event window/recurring membership, and goal horizon/notes. Gaps #1–#12 closed
> (rows 13–18 were already at parity; #19 export remains out of scope / not a
> regression). 190 backend + 109 frontend tests pass.

## Key finding

The rewrite achieved good parity on the **operational** surface (Overview, Transactions, Budgets, Recurring, Goals, Net Worth basics, Import, Insights, Settings, transfer detection, reconciliation). The big regression is the entire **Analysis tab** — the old app's analytical deep-dive — plus several individual charts.

Crucially, **the analytics engine was not touched**. Every dropped feature's computation still lives in `modules/analytics.py` and `modules/database.py`. The rewrite simply never re-exposed these functions through the FastAPI layer or built React surfaces for them. This makes reincorporation primarily a **wiring** job (thin API endpoint → React page/chart), not a re-implementation of finance logic.

Verified: `backend/` references only `find_transfer_pairs` out of the analysis-grade functions; `drill`, `compare`, `user_overlap`, `spending_by_category_over_time`, `per_day_normalize`, `count_matching_days`, `account_snapshots` have **no endpoint**, and `web/src` has zero references to drill / compare / overlap / over-time / weekday.

---

## Gap table

Legend: **GONE** = feature fully removed · **DEGRADED** = weaker version exists · **PARITY** = adequately covered (listed for completeness).

| # | Feature (old UI) | Old source | Engine function (exists) | New UI status | New gap |
|---|---|---|---|---|---|
| 1 | **Spending-by-category over time** (multi-line per category; rollup-to-parent toggle; category multiselect) | `app.py:781-816` | `spending_by_category_over_time` (`analytics.py:47`) | **GONE** | Overview shows single-month top categories (dot-matrix) only; no trend-by-category |
| 2 | **Stacked-area spending over time** (filtered) | `app.py:972-985` | `spending_by_category_over_time` | **GONE** | No stacked-area chart component or page |
| 3 | **Category → vendor drill-down** (bar charts + drill selectors + filtered rows) | `app.py:941-967` | `drill`, `vendor_of` (`analytics.py:640-655`) | **GONE** | No vendor-level analytics anywhere in new UI |
| 4 | **Compare mode** (Weekdays vs Weekends, This month vs last; per-day vs totals normalization; grouped bars) | `app.py:988-1029` | `compare`, `per_day_normalize`, `count_matching_days` (`analytics.py:592-622`) | **GONE** | No compare surface |
| 5 | **People mode** — per-category diverging (tornado) bar + mutual-spend table (Joint) | `app.py:1043-1068` | `user_overlap` (`analytics.py:826`) | **DEGRADED** | Overview dot-matrix shows total per-person split only; no per-category breakdown, no mutual table |
| 6 | **Rich Analysis filter bar** (date-range, weekday/weekend, event, specific days-of-week, non-contiguous months multiselect, categories) | `app.py:891-908` | `filter_transactions` (`analytics.py:520`) | **DEGRADED** | Transactions page has text search + category + included only |
| 7 | **Per-account balance history** line charts (one per account) | `app.py:1778-1785` | `db.account_snapshots` (`database.py:628`) | **GONE** | NetWorth shows only the aggregate net-worth trend |
| 8 | **Cumulative-savings line** overlaid on monthly net cash-flow (combo bars + line) | `app.py:748-778` | `cash_flow` (returns `cumulative`, `analytics.py:278`) | **DEGRADED** | Overview area chart plots net only; `cumulative` field returned but unused |
| 9 | **Income vs spend dual-series line** | `app.py:730-744` | `monthly_savings` (`analytics.py:62`) | **DEGRADED** | Overview shows net-area + savings-rate bars; no explicit income-vs-spend overlay |
| 10 | **Net Worth: populate month-end balances from statements** + manual as-of-date snapshot | `app.py:1703-...` | `month_end_balances` (`analytics.py:355`) | **GONE** | NetWorth supports add / edit current balance / delete only |
| 11 | **Events: date-range window & recurring-rule auto-membership** | `app.py` event manager | `event_mask` (`analytics.py:497`) | **DEGRADED** | Backend schema accepts `start_date`/`end_date`/`rule`; UI sends name+kind and does manual tagging only |
| 12 | Goal `horizon` / `notes` display | Goals tab | `goal_progress` | **DEGRADED** | `horizon` sent on create but never shown; `notes` never read/written |
| 13 | Spending alerts | `app.py:665-684` | `spending_alerts` | **PARITY** | `overview.alerts` rendered on Overview ✓ |
| 14 | Internal transfer detection + exclude | `app.py:847-875` | `find_transfer_pairs` | **PARITY** | Transactions transfer-pairs panel ✓ |
| 15 | Recurring detection / committed / anomalies | Recurring panel | `recurring_charges` etc. | **PARITY** | Recurring page ✓ |
| 16 | Budget pacing & projection | `_budgets_card` | `budget_status` | **PARITY** | Budgets PaceMeter ✓ |
| 17 | Statement reconciliation | Import | `reconcile` | **PARITY** | NetWorth reconciliation panel ✓ |
| 18 | Vendor groups / category rollups | Categories tab | — | **PARITY** | Settings rule editors ✓ |
| 19 | Data export (CSV/PDF) | — | — | **N/A** | Neither UI has it — not a regression |

**Net regressions to address:** rows 1–12 (eight GONE/partial charts + the analysis surface). Rows 1–6 are one cohesive missing area (the **Analysis / Explore** experience); rows 7–9 are missing chart overlays; rows 10–12 are smaller workflow/field gaps.

---

## Charting tech-debt note

The new UI hand-rolls SVG charts (`web/src/components/charts/`). It currently has: single-series `AreaChart`, div-based `BarChart` (single series), `DotMatrix`, `StackedBars`. Reincorporating the analysis charts needs **two new chart primitives**:

- **MultiSeriesLineChart** — N colored lines over a shared month axis (for #1, #8, #9). Extend `_svg.ts` `scale`/`toPath` helpers (already present).
- **Grouped/DivergingBarChart** — categories on one axis, two value buckets per category, one rendered as offset (Compare, #4) or mirrored negative (diverging tornado, #5).

Stacked-area (#2) can be built on the line primitive with cumulative band fills. Build these as reusable components in `web/src/components/charts/` with the existing `_svg.test.ts` math-test pattern.

---

## Reincorporation plan (phased)

Each phase follows the same shape: **(a)** add a thin FastAPI endpoint wrapping the existing `analytics.py` function (respecting `person_id` / Joint scoping like sibling routers), **(b)** add the React surface, **(c)** add a Vitest page test + `_svg` math test mirroring existing conventions. Backend-first so the frontend has real data to render against.

### Phase 0 — Scaffolding (foundation for the Analysis surface)
- New router `backend/api/analysis.py`, mounted under `/api/analysis` in `backend/main.py`.
- New page `web/src/pages/Analysis.tsx` with **sub-tabs** (Explore / Compare / People) + sidebar entry in `app-sidebar.tsx` (Money group) + route in `routes.tsx`. The sub-tabs sit below the shared FilterBar; each later phase fills one sub-tab.
- Reusable `<FilterBar>` component (date range, day-type, event, days-of-week, months, categories) backed by a new `GET /api/analysis/filter-options` (distinct months / categories / events for the persona).
- New chart primitives: `MultiSeriesLineChart`, `GroupedBarChart` (with diverging variant) in `components/charts/`, plus `_svg.ts` helper extensions and tests.
- **Deliverable:** empty Analysis page renders with a working filter bar (no charts yet).

### Phase 1 — Spending-by-category over time (gap #1, #2)
- Endpoint `GET /api/analysis/category-trend` → wrap `spending_by_category_over_time(filter_transactions(...))`; params: filters + `rollup` (parents) + `categories[]`.
- Analysis surface: MultiSeriesLineChart + "Roll up to parent groups" toggle + category multiselect; a stacked-area view toggle (gap #2).
- Tests: endpoint shape, page render, line-path math.

### Phase 2 — Category → vendor drill-down (gap #3)
- Endpoint `GET /api/analysis/drill?level=category|vendor|rows&parent=...` → wrap `drill(...)` (+ `vendor_of` with the persona's vendor rules).
- Surface: ranked horizontal bars (reuse `StackedBars` or GroupedBarChart single-series) → click a category → vendor bars → rows table (reuse the Transactions table cell renderers).
- Tests: drill levels, vendor collapsing, page interaction.

### Phase 3 — Compare mode (gap #4)
- Endpoint `GET /api/analysis/compare?preset=weekdays_weekends|month_vs_month&metric=spend|per_day` → wrap `compare` + `per_day_normalize` + `count_matching_days`.
- Surface: preset selector + measure toggle + GroupedBarChart + per-bucket total KPIs.
- Tests: per-day normalization correctness, grouped-bar math.

### Phase 4 — People / overlap deep-dive (gap #5)
- Endpoint `GET /api/analysis/overlap` (Joint only) → wrap `user_overlap(person_a, person_b)`.
- Surface: diverging (tornado) bar by category + mutual-spend table + per-person spend / shared-categories KPIs. Gate to Joint persona.
- Tests: diverging layout, shared-category detection.

### Phase 5 — Filter bar wired across analysis (gap #6)
- Ensure every Phase 1–4 endpoint accepts the full `filter_transactions` parameter set; wire `<FilterBar>` state through all Analysis sub-views.
- Optional: surface the same filter affordances (event filter, day-of-week, month multiselect) on the existing Transactions page.
- Tests: combined-filter AND semantics.

### Phase 6 — Chart overlays on existing pages (gaps #7, #8, #9)
- **#8 cumulative line:** extend Overview cash-flow chart to overlay the already-returned `cumulative` series (MultiSeriesLineChart or a second line on the area). Backend already returns it — frontend-only.
- **#9 income-vs-spend:** add an optional dual-line view to Overview (data already in `series[]` / `monthly_savings`).
- **#7 per-account history:** endpoint `GET /api/networth/accounts/{id}/history` → wrap `db.account_snapshots`; render a small AreaChart sparkline per account card on NetWorth.
- Tests: overlay rendering, per-account endpoint.

### Phase 7 — Workflow & field gaps (gaps #10, #11, #12)
- **#10:** NetWorth "populate month-end balances from statements" action → endpoint `POST /api/networth/accounts/{id}/populate-from-statements` wrapping `month_end_balances`; plus manual as-of-date snapshot endpoint.
- **#11:** wire Events create form to send `start_date`/`end_date`/`rule` (backend + `event_mask` already support it); show rule-based membership.
- **#12:** display goal `horizon` and add `notes` read/write on the Goals page.

---

## Sequencing & effort

- **Phase 0 is the gate** — both new chart primitives and the FilterBar unblock everything else.
- Phases 1–5 are the **core Analysis tab restoration** (the main regression) and should ship together to be coherent; they share the router and filter bar.
- Phases 6–7 are **independent quick wins** — #8 and #9 are frontend-only (data already flows) and could land first as low-risk confidence-builders while Phase 0 is in progress.
- Recommended order if shipping incrementally: **6 (overlays, frontend-only) → 0 → 1 → 2 → 3 → 4 → 5 → 7**.

## Risks / open questions
- **Persona/Joint scoping**: every new endpoint must mirror sibling routers' `person_id` handling (Joint = no `person_id`). Overlap (#5) is Joint-only.
- **Refund-netting & complete-month semantics** are inside the engine functions — reusing them preserves correctness; re-deriving in TS would silently diverge. Always call the engine, never recompute in the frontend.
- **Where should Analysis live? DECIDED:** a single consolidated `/analysis` page with **sub-tabs** (Explore / Compare / People), mirroring the old Streamlit tab. This keeps the old mental model and lets the `<FilterBar>` be shared across all sub-views. Phase 0 builds this page shell with the sub-tab structure; Phases 1–4 each fill one sub-tab (Phase 1–2 → Explore, Phase 3 → Compare, Phase 4 → People).
