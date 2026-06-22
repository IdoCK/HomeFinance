# HomeFinance UI Fix — Implementation Plan

**Branch:** `ui-fix` · **Goal:** bring the shipped UI up to the locked "Frosted Ledger" design.
**Design source of truth:** `.superpowers/brainstorm/2658-1781817225/content/style-zentra.html`

This is the master synthesis. Detailed analysis lives in the four section docs:
- [`01-uiux.md`](01-uiux.md) — page-by-page UX gap analysis (all 10 routes)
- [`02-frontend.md`](02-frontend.md) — styling strategy, primitives, charting, build sequence
- [`03-motion.md`](03-motion.md) — motion spec, two hero moments, reduced-motion
- [`04-finance.md`](04-finance.md) — persona rename, data-viz, financial UX conventions

---

## 1. The gap in one paragraph

The brand **tokens** (`--fl-*`, `.frosted-card`, Plus Jakarta Sans, dark mode) already exist in `web/src/index.css`, and the **data plumbing** for all 10 routes works. What's missing is the entire visual identity: the app currently reads as a generic admin-table app. The sidebar has no brand mark / persona dots / nav icons / lock footer; the Overview shows a flat KPI strip instead of the five signature cards; pages use ad-hoc inline styles with no shared primitive layer; and personas still say **You/Spouse** instead of **Ido/Aviv**.

## 2. Locked cross-cutting decisions

| Area | Decision | Source |
|---|---|---|
| **Styling** | One system: Tailwind v4 utilities driven by the existing `--fl-*` CSS vars + a thin primitive layer. Bridge shadcn's oklch semantic vars (`--card`, `--border`, `--primary`) onto the brand tokens so there's a single palette, not two. | frontend |
| **Charts** | Hand-rolled SVG — **no charting library**. The hatch pattern + dot-matrix are bespoke, data is tiny, the reference is already SVG; recharts would add ~100 KB and still need custom defs. | frontend |
| **Persona accent** | Three-way `--persona` swap with a `--persona-solid` companion (Joint's gradient can't be used where a solid color is required). Blue = Ido, Pink = Aviv, gradient = Joint. **NOT consistent with `people[0]`/`people[1]`** — the live DB orders people by id as `[Aviv(id1), Ido(id2)]`, so persona→person must resolve by identity, not row position (see Phase 0.1). | frontend / motion / finance |
| **Motion library** | CSS-first (Tailwind + already-installed `tw-animate-css`) for all chrome; a thin **lazy-loaded** `motion`/Framer layer (~20–35 KB gz) confined to chart/number primitives. Every effect additive, never load-bearing. `prefers-reduced-motion` honored globally + per-effect. | motion |
| **Persona rename** | Change the seed in `modules/database.py init_db()` from `("You","Spouse")` to `("Ido","Aviv")` **plus** an idempotent `UPDATE` to rename the existing `data/finance.db` rows (safe — all data keyed by `person_id`). Fix frontend fallbacks in `persona.tsx` & `app-sidebar.tsx`. Update name assertions in `tests/api/test_people.py`, `test_rename_person.py`, `conftest.py`. | finance |

## 3. Critical dependency — backend data contract

**The flagship Overview charts cannot show real data until `/api/overview` is extended.** Today it returns a one-month snapshot. The analytics already exist but aren't exposed:
- `analytics.cash_flow()` + per-month `savings_rate` → emit a **`series[]`** (per-month trend) for the cash-flow chart and savings-rate bars.
- `analytics.user_overlap()` → emit a Joint-only **`split[]`** (per-person spend) for the "who spent what" dot-matrix.

Change is additive: extend `backend/api/overview.py`, type the new fields in `web/src/lib/api.ts`, then build the cards. **This must land before Phase 4.**

## 4. Open questions — resolved + remaining

1. **Currency** — RESOLVED into a bigger feature. The user wants full **multi-currency** (enter any currency, per-transaction-date conversion, ILS/USD toggle, import detection). Planned separately in [`../multi-currency-plan/00-CURRENCY-PLAN.md`](../multi-currency-plan/00-CURRENCY-PLAN.md). `money.tsx` changes are owned by that plan.
2. **Events page** — RESOLVED: **keep in nav**; restyle with the frosted-card language as a top-level route (handled in Phase 5).
3. **Joint transfer double-counting:** cross-person transfers may double-count in Joint aggregates — still open; confirm desired behavior.

## 5. Phased build sequence (dependency-ordered)

Each phase is a reviewable increment. Tests assert text/testid and are mostly safe; `money.test.tsx` and the renamed-people fixtures need care.

- **Phase 0 — Persona rename (Ido/Aviv). ✅ DONE (uncommitted).** Backend seed changed to `("Ido","Aviv")` + idempotent pre-seed UPDATE migration in `modules/database.py`; frontend fallbacks in `persona.tsx`/`app-sidebar.tsx`; user-facing copy in `Import.tsx`/`README.md`; test fixtures updated. **Correction:** the live `data/finance.db` actually orders people as **id 1 = Aviv, id 2 = Ido** (not "id 1=Ido"), and all 340 transactions/4 accounts/6 imports belong to Aviv (id 1); Ido (id 2) is empty. This ordering mismatch is what Phase 0.1 corrects. *(finance §1)*
- **Phase 0.1 — Correct per-user separation (persona ↔ person ↔ color). ✅ DONE.** *Root cause:* data IS separated correctly at the DB layer (`get_transactions(person_id)` filters; Aviv=340, Ido=0, Joint=340), but `persona.tsx`/`app-sidebar.tsx` mapped personas **positionally** (`you→people[0]`, `spouse→people[1]`) while `list_people()` returns `[Aviv(id1), Ido(id2)]` — so Aviv (the only user with data) was wired to the blue "you" accent and Ido to pink, inverting the locked "Ido=blue / Aviv=pink" identity. *Fix:* resolve each persona to its person by **name** (`Ido`→you/blue, `Aviv`→spouse/pink) with a positional fallback, so attribution + color are correct regardless of DB id order. No transaction data moved (an id-swap would collide on `UNIQUE(person_id,name)` seeded categories/vendors). Regression test added in `persona.test.tsx`. *(finance §1)*
- **Phase 1 — Token bridge + primitives.** Map shadcn semantic vars onto `--fl-*`; add `--persona-solid` + `@property --persona`. Build `Card`/`CardHeaderRow`, `Pill`, `Kpi`, persona-aware `Money`. *(frontend, motion tokens)*
- **Phase 2 — App shell + sidebar.** Rounded floating frame in `routes.tsx`; sidebar identity: brand mark + "Household", segmented persona switch with colored dots, "Money" section label, nav icons, dark-ink active pill, highlighted "＋ Import", "🔒 Local only" footer. Persona-switch hero motion. *(uiux P0, motion hero #1)*
- **Phase 3 — Backend `/overview` extension.** `series[]` + Joint `split[]`; type in `api.ts`. *(§3)*
- **Phase 4 — Overview, the five signature cards.** Cash-flow hatched area chart + Ask-AI strip; This-month stacked bars; savings-rate vertical bars; who-spent-what dot-matrix; gradient AI-Insights showpiece. Overview load orchestration (card stagger, KPI count-up, chart draw-in). *(uiux P0, frontend charts, motion hero #2)*
- **Phase 5 — Page sweep.** Apply the frosted-card language + primitives to the remaining 8 routes (Transactions, Budgets, Recurring, Goals, NetWorth, Events, Import, Insights, Settings). Add Goals/NetWorth Joint comparative views; Import drag-drop; consistent skeleton/empty/error states. *(uiux P1)*
- **Phase 6 — Polish & floor.** Responsive to mobile, keyboard focus & a11y, route transitions, reduced-motion audit, remove dead inline styles. *(uiux P1, motion)*

## 6. Recommended "done" gates

- Visual diff of Overview + sidebar against `style-zentra.html`.
- `web/` vitest green (incl. updated fixtures); backend pytest green.
- Reduced-motion verified; keyboard nav verified; mobile breakpoint verified.

---
*Generated from four parallel specialist analyses (UI/UX, Frontend, Motion, Finance). Planning only — no source files were modified.*
