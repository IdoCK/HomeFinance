# UI Fix Plan — Frontend (Frosted Ledger)

**Scope:** bring `web/` up to the locked "Frosted Ledger" design (spec `docs/superpowers/specs/2026-06-18-finance-ui-rewrite-design.md`, reference `.superpowers/brainstorm/2658-1781817225/content/style-zentra.html`). PLANNING ONLY.

> Note on location: the working tree is `web/` in the repo root (`C:/Users/lahat/Documents/Claude/HomeFinance/web`), not the (empty) `ui-rewrite` worktree, which only symlinks `data/`. All paths below are repo-root-relative.

---

## 1. Current state (the gap)

- `web/src/index.css` already defines the brand: `--fl-canvas/-frame/-card/-line/-ink/-muted`, `--persona-you/-spouse/-joint`, `--pos/--neg/--saved`, `--showpiece`, `--radius-card`, plus `.frosted-card` / `.frosted-canvas`, dark-mode overrides, Plus Jakarta Sans, and tabular-nums. **Tokens are good; consumption is not.**
- Every page (`Overview.tsx`, `Transactions.tsx`, `NetWorth.tsx`, `Budgets.tsx`, …) renders with **ad-hoc inline `style={{…}}` objects** referencing the `--fl-*` vars. There is duplicated boilerplate: a `pill` CSSProperties object is re-declared in `Transactions.tsx` and `NetWorth.tsx`; a `Sparkline` SVG is hand-rolled inline in `NetWorth.tsx`; `Kpi` is a local function in `Overview.tsx`.
- shadcn primitives exist (`components/ui/card.tsx`, `table.tsx`, `badge.tsx`, `tabs.tsx`, `button.tsx`, etc.) but are **styled against the shadcn neutral/slate token set (`--card`, `--border`, oklch)** — a *second, parallel* design system that does not use `--fl-*`. `Card` is currently imported by **no page**.
- Result: three competing styling layers (inline `--fl-*`, shadcn oklch, a few `.frosted-card` classes) and **no reusable card/KPI/chart primitive layer**. None of the five signature Overview visuals (hatched cash-flow area, this-month stacked bars, savings-rate bars, who-spent-what dot-matrix, gradient AI card) exist; Overview is a plain KPI strip + category bar list.
- No charting library is installed (`package.json` has no recharts/visx). `@tanstack/react-table`, `lucide-react`, `radix-ui`, `sonner` are present.
- Persona context (`lib/persona.tsx`) only swaps `--persona` between `you` and `spouse`; **Joint never gets the gradient** (`--persona-joint`). It also keys people purely by array order (`people[0]`/`people[1]`).

---

## 2. Styling strategy decision

**Decision: one system — Tailwind v4 utilities driven by the existing `--fl-*` CSS variables, wrapped in a thin set of primitive components. Drop ad-hoc inline `style` objects; reconcile shadcn onto the `--fl-*` tokens rather than running two palettes.**

Rationale:
1. **Tailwind v4 is already the engine** (`@import "tailwindcss"`, `@theme inline`). Inline `style` objects bypass it, can't express hover/responsive/dark variants, and force every component to re-derive the same look. Utilities + `@theme` give us those variants for free and keep classes greppable.
2. **Bridge the two token sets instead of maintaining both.** In `index.css`, point the shadcn semantic vars at the brand: `--card: var(--fl-card)`, `--border: var(--fl-line)`, `--background: var(--fl-frame)`, `--foreground: var(--fl-ink)`, `--muted-foreground: var(--fl-muted)`, `--radius: var(--radius-card)`, and `--primary: var(--persona)` (so shadcn focus rings/buttons follow the active persona). After this, shadcn's `Card`, `Button`, `Table`, `Badge` automatically look "Frosted Ledger" and we don't fork them.
3. **Expose brand-only tokens to Tailwind** via `@theme inline` so utilities exist: add `--color-persona: var(--persona)`, `--color-pos: var(--pos)`, `--color-neg: var(--neg)`, `--color-saved: var(--saved)`, `--color-fl-muted: var(--fl-muted)`, `--color-fl-line: var(--fl-line)`, `--color-fl-ink`, `--color-fl-card`. That yields `text-persona`, `bg-persona`, `border-fl-line`, `text-fl-muted`, etc. The `--persona` swap at runtime keeps working because Tailwind compiles to `var(--color-persona)` → `var(--persona)`.
4. **`.frosted-card` becomes a primitive, not a class scattered in JSX.** Keep the class as the visual definition; surface it through a `<Card>` primitive (see §3) so pages never hand-write `className="frosted-card" style={{padding:24}}`.

This stays fully compatible with shadcn + Tailwind v4 (we only remap existing vars; no shadcn component API changes) and removes the inline-style layer entirely. `cn()` (`lib/utils.ts`) is already available for class merging.

Migration tactic: introduce primitives first, then mechanically replace inline styles page-by-page. The visible look should be near-identical after the token bridge, so test snapshots/queries (which assert on text and `data-testid`, not class names — see `Overview.test.tsx`, `money.test.tsx`) keep passing. **One exception:** `money.test.tsx` asserts `toHaveStyle({ color: "var(--neg)" })`; keep `Money` emitting an inline color (or update that test in the same commit — see §7).

---

## 3. Reusable primitive components to build

All under `web/src/components/`. Charts under `web/src/components/charts/` (the spec's planned path, §2 / §8). Props described at the interface level.

**Layout / chrome (`components/ui/` — reuse shadcn, lightly extend):**
- `Card`, `CardHeader`, `CardTitle`, `CardContent` — **reuse existing `ui/card.tsx`** once tokens are bridged; add a `frosted` look by default (rounded-[--radius-card], ring/shadow per `.frosted-card`). Add a small `CardHeaderRow` convenience (title left + `···`/action right) matching `.ch` in the reference.
- `Pill` (`components/ui/pill.tsx`) — replaces the duplicated `pill` CSSProperties. Props: `as?`, `active?`, `children`. Used by month stepper, filter selects, compare/granularity controls.

**Data display (`components/`):**
- `Kpi` (`components/kpi.tsx`) — promote the local `Overview` `Kpi`. Props: `label: string`, `big?: boolean`, `colored?: boolean`, `testId?: string`, `children`. Uppercase label + bold tabular value.
- `Money` (`components/money.tsx`) — **already exists**; extend to be persona-aware optional: add `accent?: boolean` to render in `--persona`. Keep `formatMoney`. Keep colored-negative behavior.
- `SectionTitle` / tiny uppercase label — trivial, can live in `kpi.tsx`.

**Charts (`components/charts/`, hand-rolled SVG — see §4):**
- `AreaChart` (`area-chart.tsx`) — the **hatched cash-flow** card visual. Props: `points: {label?: string; value: number}[]`, `accent?: string` (defaults `--persona`), `height?`. Renders the reference's three-layer SVG: gradient fill (`linearGradient`), `pattern` hatch overlay (45°), and a stroke polyline. Step or smooth via a `mode` prop.
- `StackedBars` (`stacked-bars.tsx`) — the **"This month"** Income/Spending/Saved rows: each row = label + value + a `bar` track with a colored fill `i`. Props: `rows: {label; value; pct; color}[]`. (Reference `.ln`/`.bar`.)
- `BarChart` (`bar-chart.tsx`) — the **savings-rate** pink bar history. Props: `series: {label: string; value: number; highlight?: boolean}[]`, `color?`, `highlightColor?`. X-axis labels row. (Reference `.bars`/`.xax`.)
- `DotMatrix` (`dot-matrix.tsx`) — the **who-spent-what** Joint signature. Props: `segments: {value: number; color: string; label: string}[]`, `dots?` (default ~21). Computes dot counts proportionally; renders a flex-wrap dot grid + legend with bold totals. Single-persona mode: caller passes that person's category split instead (per spec §5 fallback). Keep the "single split bar" fallback as a `variant="bar"` prop.
- `GradientCard` (`components/gradient-card.tsx`) — the **AI Insights showpiece**. Wraps content in the `--showpiece` radial gradient with the glassy `::after` highlight and white text; a pill tag slot. Props: `tag?`, `headline`, `children`. The *only* place the gradient is used.

**Sparkline:** the inline `Sparkline` in `NetWorth.tsx` is subsumed by `AreaChart` (line-only `mode`), or extract a minimal `Sparkline` into `charts/`. Net Worth should consume the shared one.

---

## 4. Charting approach

**Decision: hand-rolled SVG primitives (no charting library).**

Tradeoffs considered:
- **recharts** (the shadcn `@shadcn/chart` wrapper, ~100 KB+ gzipped w/ d3 deps): great for standard area/bar charts, but **the four signature visuals are non-standard** — a 45° `<pattern>` hatch fill, a proportional **dot-matrix**, fixed stacked mini-bars, and a small savings-bar strip. recharts fights you on the hatch (custom `<defs>`/`<Customized>`) and gives nothing for the dot-matrix. We'd pull a large dep and still hand-write the distinctive parts.
- **visx** (lower-level d3 primitives): more flexible but heavier conceptual surface and more deps than this app needs for ~5 small charts.
- **Hand-rolled SVG**: the reference *is already hand-rolled SVG* (lines 146–159 are a copy-pasteable `<path>`/`<pattern>`/`<polyline>`), the existing `NetWorth` Sparkline proves the pattern works here, data volumes are tiny (≤~12 months, a handful of categories), and we keep bundle size flat. Cost: we write axis/scale helpers ourselves, but for these specific bespoke visuals that's *less* code than bending a library. No animation/tooltip library needs — a CSS transition and a `<title>` suffice.

Put a tiny shared `scale(values, range)` + `toPath(points)` helper in `components/charts/_svg.ts`.

If a future page needs a generic interactive multi-series chart, revisit adding recharts then (`@shadcn/chart`), scoped to that page only.

---

## 5. Persona wiring

Current (`lib/persona.tsx`): sets `data-persona` and swaps `--persona` between `--persona-you` and `--persona-spouse`; **Joint falls through to `--persona-you`** (the `else` branch only checks `spouse`). The seam gradient and Joint accent never appear. `personId` keys off `people[0]/[1]`.

Changes (interface-level):
- In the persona `useEffect`, set `--persona` for all three: `you → var(--persona-you)`, `spouse → var(--persona-spouse)`, `joint → var(--persona-joint)` (the blue→pink gradient already defined in `index.css`).
- **Caveat:** `--persona-joint` is a `linear-gradient`, so it can't be used directly as a solid `color`/`background-color`. Provide a paired solid fallback var, e.g. set `--persona-solid` (a mid blue-violet, e.g. `#7C6FF0`) alongside `--persona`, and have primitives use `background: var(--persona)` where a gradient reads well (sidebar seam, active pill, bars) but `color: var(--persona-solid)` for text/borders. Document this split in `index.css` next to the tokens. The persona-aware `Money accent` and active-nav text use `--persona-solid`; fills (pill bg, dot-matrix, seam) use `--persona`.
- Sidebar (`components/app-sidebar.tsx`): the `data-persona-seam` attr already exists; add a CSS rule (or `border-left`/left-edge bar) keyed on `[data-persona-seam="you|spouse|joint"]` to render the **ledger seam** (solid blue / solid pink / gradient) — the spec's signature §3.1. Persona tabs already color the active one with `--persona`; keep, but use the gradient for Joint.
- Keep the `people[0]/[1]` ordering assumption (it matches `database.py` semantics and `Transactions.tsx`'s `personaColor`), but extract `personaColor(personId, people)` (currently duplicated in `Transactions.tsx`) into `lib/persona.tsx` and reuse in `DotMatrix`/Net Worth. Note the known ceiling (3rd+ person → hairline) already documented in `Transactions.tsx`.

---

## 6. File-by-file refactor list & build sequence

Dependency-ordered, sized into reviewable increments (each ~one PR/commit, tests green at every step).

**Increment 1 — Token bridge & Tailwind exposure (no visual change intended).**
- `web/src/index.css`: map shadcn vars → `--fl-*`; add `@theme inline` color tokens (`--color-persona`, `--color-pos/neg/saved`, `--color-fl-*`); add `--persona-solid`; add `[data-persona-seam]` seam rules. 
- Verify all existing tests still pass (look identical).

**Increment 2 — Primitive layer.**
- New: `components/ui/pill.tsx`, `components/kpi.tsx`, `components/gradient-card.tsx`, `components/charts/_svg.ts`, `area-chart.tsx`, `stacked-bars.tsx`, `bar-chart.tsx`, `dot-matrix.tsx` (+ optional `sparkline.tsx`).
- Extend `components/money.tsx` (`accent` prop). Extend `components/ui/card.tsx` (frosted default + `CardHeaderRow`).
- Add focused unit tests for `AreaChart` path generation, `DotMatrix` proportional counts, `BarChart` highlight (pure functions — easy to test).

**Increment 3 — Persona + Sidebar.**
- `lib/persona.tsx`: three-way `--persona` swap + `--persona-solid`; export shared `personaColor`.
- `components/app-sidebar.tsx`: replace inline styles with utilities/`Pill`; wire the ledger seam; add the "Money / Utility" nav group labels + divider + lock footer from the reference (lines 109–120). Keep `NavLink`s and the existing `Events` route.
- Update `routes.tsx` `AppLayout` to use the frame layout (canvas → rounded frame → sidebar + main) per reference `.frame`.

**Increment 4 — Overview (the showpiece page).**
- Rebuild `pages/Overview.tsx` to the 2-row grid: Row 1 = Cash flow (`AreaChart` hatched + In/Out/Net `Kpi`s + AI explore input) 2/3, This-month (`StackedBars` + big net + delta) 1/3. Row 2 = Savings rate (`BarChart`), Who-spent-what (`DotMatrix`), AI Insights (`GradientCard`). Keep the alert chips (already present) and `month` stepper (now a `Pill`).
- **Backend dependency (flag to backend plan):** `GET /api/overview` (`backend/api/overview.py`) currently returns only the *selected* month's scalars + `by_category` + `months` list. The cash-flow area and savings-rate bars need a **per-month trend series** (income/spend/net/savings_rate across `months` — already computed in `recs` but dropped at line 42), and the dot-matrix needs a **per-person split** for the month (Joint view). Without these the charts have no data. Either extend the endpoint to return `trend: [...]` and `by_person: {you, spouse}`, or (interim) the Overview can derive bars from a sequence of `getOverview` calls — extending the endpoint is far cheaper. Record this as the cross-cutting backend item.
- Update `Overview.test.tsx`: it asserts `getByTestId("income"/"spend"/"net")`, `52%`, and `Housing`. Preserve those `data-testid`s and the category label in the new layout so the test passes (or extend the test alongside).

**Increment 5 — Remaining pages (mechanical inline-style → utility/primitive sweep), one commit each:**
- `pages/Transactions.tsx` — swap local `pill`, header inline styles, sort-header styles to `Pill`/utilities; reuse shared `personaColor`. (Keep the TanStack table logic.)
- `pages/NetWorth.tsx` — replace inline `Sparkline` with shared chart; `pill`/`badge` → primitives.
- `pages/Budgets.tsx`, `pages/Goals.tsx`, `pages/Recurring.tsx`, `pages/Events.tsx`, `pages/Import.tsx`, `pages/Insights.tsx`, `pages/Settings.tsx` — same sweep; `Insights` adopts `GradientCard`; `Import` uses `Card`/`Pill` for the wizard chrome.
- Each page already has a sibling `*.test.tsx`; run after each commit.

**Increment 6 — Cleanup.** Remove dead inline-style patterns, dedupe any remaining `pill`/`badge` literals, ensure no page imports leftover ad-hoc style objects. Confirm `lucide-react` icons replace the unicode glyphs in nav if desired (optional polish).

---

## 7. Testing approach

- Existing setup: **Vitest + Testing Library + jsdom** (`vitest run`, `web/src/test/setup.ts`, `@testing-library/jest-dom`). 12 `*.test.tsx`/`.test.ts` files exist and must stay green. They assert on **text content, `data-testid`, roles, and aria-labels** — not class names — so the utility refactor is largely safe. Preserve: Overview's `data-testid="income|spend|net"` + `"52%"` + `"Housing"`; persona test's behavior; Transactions/Budgets/etc. queries.
- **One test needs a same-commit touch:** `money.test.tsx` asserts `toHaveStyle({ color: "var(--neg)" })`. Keep `Money` emitting the inline color for negatives (cheapest — preserves the test), and add the new `accent` path separately.
- **New tests** (pure-function-first, per project TDD): `AreaChart` `toPath` output for a known series; `DotMatrix` dot allocation sums to total and respects ratios; `BarChart` highlight flag; persona `--persona`/`--persona-solid` swap for all three keys (extend `persona.test.tsx`).
- Run `npm test` in `web/` after every increment; do not introduce snapshot tests on class strings (brittle under utility churn).
- Out of scope here (backend plan): the `/api/overview` `trend`/`by_person` additions need their own FastAPI `TestClient` test.

---

## 8. Risks / call-outs

- **Backend data gap is the critical-path dependency for Overview** (§6 Increment 4): the two flagship charts cannot render real data until `/api/overview` returns a trend series + per-person split. Sequence the backend change before/with Increment 4.
- `--persona-joint` being a gradient (not a color) is the main persona footgun — handled via the `--persona-solid` pairing (§5).
- Token-bridge increment must be verified visually + by tests *before* the page sweep, or regressions compound.
- Keep the gradient strictly to `GradientCard` (AI Insights) — the spec spends its boldness there and nowhere else.
