# Chart Platform — Research Summary & Design Plan

Goal: stop hand-rolling every chart, add real interactivity (hover/crosshair/tooltips,
legend toggling, keyboard a11y), and let users **build and save their own charts** —
all without losing the "Frosted Ledger" identity or the app's honesty conventions.

Two inputs feed this doc:
1. **In-house + online research** by the `dashboard-graphs-advisor` agent.
2. A **frontend-design planning pass** (interactivity model + chart-builder UX +
   rollout), below.

---

## Part 1 — Research summary

### What we have today (in-house audit)

- ~1,000 LOC of **dependency-free, hand-rolled SVG** in `web/src/components/charts/`:
  `area`, `line`, `bar`, `stacked-bars`, `dot-matrix`, `diverging-bar`,
  `grouped-bar`, `sparkline`, `legend`, sharing `_svg.ts` (scales/paths/partial-split).
- **Interactivity ≈ none.** No hover, crosshair, or tooltip on the SVG charts — only a
  static last-point label and native `title` tooltips on div-based bars/dots. On a
  multi-month, multi-category line you **cannot read a mid-series month's value**. This
  is the biggest functional gap.
- **A11y is image-level only** (`role="img"` + one `aria-label`); no keyboard traversal
  or screen-reader data table. (One genuine strength: legend/dot **shape** cues, not just
  color — ahead of most libraries. Keep them.)
- **Axes are minimal**; x-positions are index-based (assume evenly-spaced, equal-length
  series). Each chart re-implements its own `ResizeObserver`.
- `bar-chart.tsx` is **production-dead** (imported by tests only) — decide delete vs. wire up.

### House conventions any library MUST respect (non-negotiable)

These are correctness/identity rules, not styling preferences:

- **Persona discipline** — `--persona-you` (#3B82F6 Ido/blue), `--persona-spouse`
  (#EC4899 Aviv/pink), `--persona-joint` gradient (+ `--persona-joint-solid` for
  strokes). The category ramp `CATEGORY_COLORS` (`_svg.ts:58-69`) **deliberately excludes
  the persona hues** so a category can never masquerade as a person. A library's default
  palette would violate this.
- **Partial-month honesty** — the settled prefix renders solid; the in-progress tail
  renders **dashed + lower-opacity** (`splitPartialPath`), labels append "so far". This is
  the app's signature truth-telling device.
- **Zero baseline always in the y-domain** — charts never truncate the axis to exaggerate
  a trend; a heavier zero gridline is drawn.
- **All value formatting routes through `formatMoney`** (currency-toggle aware, USD↔ILS).
- **Reference/benchmark lines** — savings-rate 20% / 50%-FIRE, net-worth milestones.
- Theme everything from `--fl-*` / `--persona-*` CSS vars so **dark mode flips for free**.
  The `--showpiece` gradient is reserved for AI Insights — charts must not use it.

### Library research (2026)

| Library | Render | Interactivity | A11y | Identity fit | Bundle | Verdict |
|---|---|---|---|---|---|---|
| **Recharts v3** | SVG | Built-in tooltips/hover/legend toggle/brush | `accessibilityLayer` (kbd+SR) | High — custom `<defs>`, dashed segments, `ReferenceLine` | ~50 kB gz tree-shaken | **Primary** |
| **visx** | SVG (headless) | DIY | DIY | Maximum (you draw it) | smallest (~15 kB) | **Fallback / showpiece only** |
| Nivo | SVG/Canvas | Strong | Good | Opinionated; hatch/dashed awkward | ~186 kB | No |
| ECharts | Canvas | Best-in-class | ARIA module | Canvas fights CSS-var theming | ~100 kB gz | Overkill |
| Chart.js | Canvas | Good | Weak | Canvas fights identity | moderate | No |
| Tremor | SVG (Recharts) | Good | Good | Lowest — pre-styled | ~50–200 kB | No (just use Recharts) |
| Observable Plot | SVG | Limited | Immature | Rough React embed | — | No |

**Decisive fact:** shadcn/ui's official `Chart` component **is Recharts v3**, themed entirely
through CSS variables, with `accessibilityLayer`. HomeFinance is already a shadcn SPA, so
this is the lowest-friction path and our tokens wire in directly.

### Recommendation: **library-first — minimize hand-rolled charts**

> **User directive:** keep hand-rolled code to an absolute minimum. Reproduce the house
> conventions *inside* Recharts rather than preserving bespoke SVG.

1. **Adopt Recharts (via shadcn Chart) for everything we can** — line, area, bar,
   stacked, grouped, sparkline, and the signatures: the **partial-month dashed tail**
   (second `<Line>`/`<Area>` segment with `strokeDasharray`), **persona-gradient strokes**
   (SVG `<linearGradient>` in `<defs>`, `stroke="url(#id)"`), and the **diverging/tornado**
   (signed bars). Plus all user-built charts.
2. **Keep hand-rolled only where a library genuinely can't express it** — currently just
   `dot-matrix` (proportional isotype dot grid; not a chart-library primitive). Re-evaluate
   even this if a clean Recharts/`<Customized>` route appears.
3. **Fallback to visx** only if a specific Recharts chart can't hit fidelity after a real try.

### Blockers / guardrails to budget for

- **Test rewrite (blocker):** ~65 structural assertions (exact path counts, `data-*`
  hooks) break on any swap. Rewrite chart tests against the library's DOM *and* against
  behavior (tooltip shows correct `formatMoney` value), not path geometry.
- **Honesty guardrails (blocker):** enforce in a shared wrapper — zero-baseline always,
  `formatMoney` on every tick/tooltip, `CATEGORY_COLORS` (no persona hues for categories).
- **De-risk first:** prototype the **dashed partial tail** and **persona-gradient stroke**
  in Recharts before committing — these are the two hardest conventions to reproduce.

---

## Part 2 — Frontend-design plan

No new palette or type system is invented here — the **Frosted Ledger identity is already
established** (frosted-glass cards, persona inks, big bold tabular-nums, hatch textures,
the dashed "so far" honesty tell). The design work is in two new surfaces that must feel
native to it: the **interaction layer** and the **chart-builder**.

### 2a. The interaction layer — a shared `<ChartFrame>` + "ledger slip" readout

Every chart (built-in *and* user-built) renders inside one shared wrapper so interactivity
and honesty guardrails live in exactly one place.

**Signature: the tooltip as a "ledger slip."** Instead of a generic floating box, the
hover readout is styled like a slip torn from the household ledger — which is literally
what this app is:

```
            ┌─────────────────────────────┐
  crosshair │  MAR 2026          so far ▍  │  ← eyebrow month · "so far" stamp if partial
   (hair-   │  ─────────────────────────  │  ← hairline rule (--fl-line)
    line) ──┤  ● Groceries        $1,240  │  ← shape swatch · name · right-aligned
            │  ● Transport          $380  │     tabular-nums value (formatMoney)
            │  ◆ Dining             $295  │
            └─────────────────────────────┘
```

- Vertical **crosshair** snaps to the nearest month; a filled focus dot appears on each
  series at that x.
- Slip is a `frosted-card` (inherits dark-mode), rows sorted by value desc, each row =
  `shape swatch · series name · right-aligned formatMoney`. The **shape** swatch (not just
  color) carries the existing a11y strength forward.
- Partial month → a small **"so far" stamp** in the eyebrow (reuses the honesty tell).

**Legend becomes interactive:** click a series to toggle it, hover to highlight (dim the
rest). Reuses the existing `Legend` shapes.

**Keyboard a11y (closes the biggest gap):** the chart is focusable; ◀ ▶ move the crosshair
month-by-month, ▲ ▼ cycle the focused series, and an `aria-live` region announces
"March 2026 — Groceries $1,240." A visually-hidden `<table>` mirrors the series for
screen readers.

**Restraint:** the crosshair is one hairline, the slip is quiet, motion is a fast fade
(respect `prefers-reduced-motion` — appear instantly). The boldness is spent on the slip
metaphor, nothing else.

### 2b. The chart-builder — "Studio"

A new surface (Utility nav, wand/`+` icon) where users compose a chart from plain choices
and pin it. Config rail on the left, **live frosted preview** on the right that re-renders
on every change — the preview *is* the hero.

```
┌── Studio ───────────────────────────────────────────────────────────┐
│  "Spending, by category, last 12 months — as a line."   ← NL summary │  ← signature
│                                                                       │
│  ┌── Build ────────────┐   ┌── Live preview ────────────────────┐    │
│  │ Measure   [Spending▾]│   │                                    │    │
│  │ Split by  [Category▾]│   │     (real <ChartFrame> render,     │    │
│  │ Over      [12 mo  ▾] │   │      fully interactive, themed)    │    │
│  │ As a      [Line  ▾]  │   │                                    │    │
│  │ Person    [Joint ▾]  │   │                                    │    │
│  │                      │   └────────────────────────────────────┘    │
│  │ Title […]            │   [ Pin to My Charts ]   [ Discard ]        │
│  └──────────────────────┘                                             │
└───────────────────────────────────────────────────────────────────────┘
```

**Signature: the natural-language sentence.** The config compiles to one readable line —
*"Spending, by category, last 12 months — as a line."* It makes an abstract spec legible,
doubles as the default title, and is the memorable, on-brand element (a ledger speaks in
plain English about money, not "x-axis / series").

**Honest defaults baked into the builder:** invalid combinations are *disabled, with a
reason*, never silently wrong — e.g. "Savings rate" is a ratio, so "Donut" greys out
("a rate can't be a share of a whole"); "Net worth" defaults to area-over-time. This keeps
chart-choice correctness (the advisor's concern) inside the product, not just in review.

**Pinned charts → "My Charts" board:** saved specs render on a board the user can reorder;
optionally surface a pinned chart on Overview. Persistence is **localStorage** — consistent
with the app's "🔒 Local only" promise and data-minimized ethos (no server round-trip, no
new data leaves the device).

### 2c. Architecture (how the two surfaces share one engine)

```ts
// One spec describes any chart — built-in or user-built.
type ChartSpec = {
  id: string;
  title: string;            // defaults to the NL summary
  metric: 'spend' | 'income' | 'net_saved' | 'savings_rate' | 'net_worth' | 'account_balance';
  dimension: 'none' | 'category' | 'person' | 'account';
  kind: 'line' | 'area' | 'bar' | 'stacked_bar' | 'donut';
  range: { months: number } | { from: string; to: string };
  persona?: PersonaKey;     // optional per-chart override of the global persona filter
};
```

- **Resolver** `specToSeries(spec)` reuses existing API/aggregation to produce series
  `{ name, values[], color, partial[] }` — the same shape today's charts already consume,
  so the partial-month + persona conventions carry through unchanged.
- **`<ChartRenderer spec>`** picks the Recharts component for `kind`, wraps it in
  `<ChartFrame>`, and applies the guardrails (zero-baseline, `formatMoney`, `CATEGORY_COLORS`).
- **Compatibility matrix** drives which (metric × dimension × kind) combos are valid — the
  same table powers the builder's greying-out and prevents nonsense charts.
- A `chart-theme.ts` maps `--persona-*` / `--fl-*` / `--pos|neg|saved` into the shadcn
  Chart config so Recharts and the hand-rolled signatures stay visually identical.

### 2d. Rollout (dependency-ordered)

- **P0 — Infra + interactivity (no user-facing new feature yet).**
  Add shadcn Chart (Recharts v3) + `chart-theme.ts`. Build `<ChartFrame>` (ledger-slip
  tooltip, crosshair, legend toggle, keyboard a11y). Migrate the **standard line consumers**
  (Analysis trend, Overview category + savings-rate) behind the frame. Keep hand-rolled
  signatures. Prototype the dashed partial tail + persona-gradient stroke first to de-risk.
  Rewrite affected tests to behavior-based assertions.
- **P1 — Chart-builder.** `ChartSpec` + resolver + compatibility matrix + `<ChartRenderer>`.
  Studio page with NL summary + live preview; pin → localStorage; "My Charts" board.
- **P2 — Polish.** Donut/extra kinds, add-pinned-chart-to-Overview, drag-reorder, export
  PNG/CSV, "so far" stamp parity across all kinds.

### Guardrails checklist (carry into every PR)

- [ ] Zero baseline always in the y-domain (no truncated axes).
- [ ] Every tick/tooltip value through `formatMoney` (currency-toggle correct).
- [ ] Categories use `CATEGORY_COLORS` — never a persona hue.
- [ ] Partial months render dashed + "so far"; honesty preserved on migrated charts.
- [ ] Dark mode verified (tokens, not library defaults).
- [ ] Keyboard + screen-reader path verified on `<ChartFrame>`.
- [ ] Chart-correctness questions (is the *number* right?) routed to the finance advisors,
      not assumed.

---

_Sources: dashboard-graphs-advisor report (in-house code audit) + 2026 library research
(LogRocket, PkgPulse, Chart.ts, usedatabrain, shadcn/ui docs, airbnb/visx, recharts releases)._
