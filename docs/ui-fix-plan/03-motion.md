# 03 — Motion & Interaction Spec ("Frosted Ledger")

Motion design for the HomeFinance React SPA (`web/`). The brief is **restraint over scatter**: a calm, premium ledger that feels physical and alive in two or three places, and otherwise stays still. Money apps lose trust when they feel jittery; every effect below is deliberately conservative.

---

## 0. Foundations

### 0.1 Library recommendation — **CSS-first + a thin `motion` (Framer Motion) layer for the two hero moments**

| Approach | Use it for | Why |
|---|---|---|
| **Pure CSS / Tailwind + `tw-animate-css`** (already a dep) | hover/press, skeletons, persona accent morph, route fade, card stagger | Zero added bundle, GPU-cheap, respects `prefers-reduced-motion` via media query for free. The accent morph is *just a CSS variable transition* — no JS needed. |
| **`motion`** (Framer Motion v11+, the `motion` package) — lazy-loaded | KPI count-up, SVG chart draw-in, bar/dot-matrix stagger | These need value interpolation + orchestration that CSS can't express cleanly. ~`motion/react` tree-shakes to ~18–34 KB gz when you import only `motion` + `animate`/`useInView`. |

**Decision:** do **not** reach for Framer Motion globally. Wrap chart/number primitives in small motion components; keep the chrome (sidebar, nav, cards, routes) on CSS. This keeps the added JS confined to the Overview + Net Worth charting code, which is the only place orchestration earns its weight. Avoid `react-spring`/`gsap` — heavier, redundant here.

**Tradeoffs:** the cost of `motion` is ~20–35 KB gz + a dependency to maintain. We accept it for the dashboard charts only. If bundle pressure ever spikes, the count-up and draw-in can fall back to a 40-line `requestAnimationFrame` hook and `motion` can be dropped — design degrades gracefully because every motion is additive, never load-bearing.

### 0.2 Motion tokens (add to `index.css`)

```css
:root {
  /* durations */
  --m-fast:   120ms;  /* press, pill toggle */
  --m-base:   200ms;  /* hover, nav, route fade */
  --m-accent: 320ms;  /* persona accent morph */
  --m-reveal: 480ms;  /* card / chart entrance */
  --m-count:  900ms;  /* KPI count-up */

  /* easings */
  --ease-out:   cubic-bezier(0.22, 1, 0.36, 1);   /* entrances, expansive */
  --ease-inout: cubic-bezier(0.4, 0, 0.2, 1);     /* state changes */
  --ease-press: cubic-bezier(0.34, 1.56, 0.64, 1);/* tiny overshoot, press only */

  --stagger: 60ms; /* per-item delay in any sequence */
}
```

### 0.3 Global rules
- **Animate only `transform`, `opacity`, `color`, `background-color`, `box-shadow`, and SVG `stroke-dashoffset`.** Never animate `width`/`height`/`top`/`left` for layout (bars use `transform: scaleY`, not `height`).
- Entrance distances are tiny: **8–12px**, never more. Premium = subtle.
- Nothing loops except the skeleton shimmer. No infinite ambient motion.
- Respect `will-change` only during the animation, then drop it.

### 0.4 `prefers-reduced-motion` — global contract (mandatory)
A single global block neutralizes all *movement and looping* while **preserving final state and color**:

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
    scroll-behavior: auto !important;
  }
}
```

Per-effect reduced-motion behavior is restated in each section, but the rule is uniform: **translate/scale/draw → none (snap to final); color/opacity cross-fades → kept but instant or ≤80ms; count-up → render final number directly; skeleton shimmer → static muted block, no pulse.** The `motion` components must read `useReducedMotion()` and skip interpolation, rendering the resolved value on first paint.

---

## 1. Page-load orchestration — Overview (HERO #1)

This is the first thing both users see each session. It is the primary investment.

**Sequence (total ≈ 1.0s, fully readable by ~500ms):**

1. **Frame is instant.** Sidebar and top bar do **not** animate on load — chrome is stable furniture. Animating it every navigation gets tiring fast.
2. **Card stagger reveal.** Each top-level `.frosted-card` / `section`:
   - properties: `opacity 0→1`, `transform: translateY(10px)→0`
   - duration `--m-reveal` (480ms), `--ease-out`
   - stagger `--stagger` (60ms) in DOM order: alerts row → KPI strip → cash-flow card → this-month card → row-2 cards. Cap the *visible* stagger at ~6 items / 360ms so nothing feels slow.
3. **KPI count-up** (the big numbers — Net, Income, Spending, Savings rate):
   - starts when its card's reveal is ~halfway (≈240ms in), so the number is already visible then "settles."
   - count from 0 → value over `--m-count` (900ms), `--ease-out` so it decelerates into the final figure.
   - **tabular-nums already set** — good, digits won't reflow. Format with the same `formatMoney`; animate the underlying number, not the string.
   - the small percent delta pill (`▲ 15%`) fades in at the *end* of the count-up (+80ms), so the eye reads the figure first, then the context.
4. **Chart draw-in** (cash-flow area path):
   - line: animate SVG `stroke-dashoffset` from `pathLength`→0 over 700ms, `--ease-out`.
   - area fill (`url(#ar)` + hatch): `opacity 0→1` over 500ms, starting 200ms *after* the line begins, so the stroke "leads" and the fill "floods in" behind it.
   - **no left-to-right clip-reveal** of data points — for a household ledger, the honest read is the whole shape appearing, not a fake "live drawing."
5. **Savings-rate bars** (pink): each bar `transform: scaleY(0)→1`, `transform-origin: bottom`, 420ms `--ease-out`, stagger 50ms left→right. The current month bar (`.now`) lands last and gets a +40ms hold then a 1px settle — a quiet emphasis.
6. **Dot-matrix fill** ("Who spent what" — the Joint signature): dots fade+scale in (`opacity 0→1`, `scale 0.6→1`, 260ms) staggered 18ms each, **in spend order** (all "you" blue dots, then "spouse" pink) so the proportion reads as it fills. This tiny sequence is the most charming non-hero moment — keep its per-dot delay short so the whole matrix completes in <450ms.

**Reduced motion:** all cards, numbers, paths, bars, dots render in final state on first paint. KPIs show the final figure (no roll). Dot matrix appears complete.

**One-shot only:** orchestration runs on mount, not on every persona switch or month change (those use §2 / §5).

---

## 2. Persona-switch transition — the signature moment (HERO #2)

Triggered by the segmented control (You / Spouse / Joint). This is the brand's emotional core: the whole app "becomes" that person.

**What animates — the accent, smoothly, everywhere at once:**
- The mechanism is the existing `--persona` CSS variable (set in `persona.tsx`). Add a transition on the variable's *consumers*, not a JS tween. Any element using `var(--persona)` for `color` / `background` / `border` gets `transition: color var(--m-accent) var(--ease-inout), background-color var(--m-accent) var(--ease-inout), border-color var(--m-accent) var(--ease-inout);`.
  - **CSS-variable transition caveat:** transitioning a raw `--persona` value doesn't animate intermediate colors. To get a true blue↔pink *morph*, register it as an animatable custom property:
    ```css
    @property --persona { syntax: '<color>'; inherits: true; initial-value: #3B82F6; }
    ```
    Then a change to `--persona` interpolates through the color space over `--m-accent`. (Joint is a gradient, not a color — see below.)
- **Sidebar:** active persona pill background slides — animate the *selected* indicator with a shared moving highlight (a single absolutely-positioned `<span>` that translates X between the three segments, 280ms `--ease-inout`), rather than cross-fading three backgrounds. The moving pill is the satisfying part.
- **Active nav item & active-state tints** recolor via the `@property` morph (320ms).
- **Charts:** the cash-flow line stroke, area gradient stops, category bars, and the savings bars recolor over `--m-accent`. For SVG gradient stops, drive their `stop-color` off `var(--persona)` too, or `motion`-animate the stop colors in the charting components for a guaranteed smooth blend.
- **Joint = blue→pink gradient.** You can't interpolate a solid into a gradient cleanly. Handle Joint by **cross-fading two stacked layers**: keep the solid-accent layer and a gradient layer, and animate their `opacity` (300ms) when entering/leaving Joint. Going You→Spouse is a pure color morph; anything ↔ Joint is a gradient cross-fade. This is the one place worth the extra DOM.

**What must NOT animate:**
- **No layout shift, no card re-stagger, no re-mount.** Switching persona must feel like a *recolor*, not a page reload. Data values may change (different person's numbers) — let numbers **cross-fade in place** (120ms opacity dip) or, if the figure changes, a *short* 400ms count from old→new value. Do **not** re-run the full §1 entrance.
- No motion on the sidebar brand, the nav icons' positions, or the frame.
- Don't animate text content character-by-character.

**Duration budget:** the whole switch resolves in ≤320ms. It should feel immediate but liquid.

**Reduced motion:** accent color and gradient swap instantly; the moving sidebar pill jumps to its segment; number changes snap. No interpolation, but the *result* is identical so the feature still communicates identity.

---

## 3. Route transitions — between the 10 pages

Keep these nearly invisible; they happen constantly.

- **Cross-fade + 6px rise on the `<Outlet>` content only** (sidebar persists, never transitions). On route change: outgoing `opacity 1→0` (100ms), incoming `opacity 0→1` + `translateY(6px)→0` (200ms `--ease-out`). Net ~220ms.
- Implement with `motion`'s `AnimatePresence` keyed on `location.pathname` wrapping the `Outlet`, **or** a CSS approach: a `key`-ed wrapper with a `@keyframes route-in` applied on mount. Given the rest of the chrome is CSS, the CSS-keyframe version is preferred to avoid pulling `AnimatePresence` into the layout.
- **Landing on Overview re-triggers §1 orchestration** (it's the dashboard, it earns a reveal). All other pages get only the plain route fade — their internal content uses the lighter §1-style card fade *without* count-up/draw-in unless they have their own charts (Net Worth, Budgets).
- No directional slide (no "back = slide right"). This is a tool, not a phone OS; slides would feel gimmicky across 10 peer pages.

**Reduced motion:** instant swap, no fade, no rise.

---

## 4. Hover / press micro-interactions

All subtle, all `--m-fast`/`--m-base`. These give the surface "give" without noise.

| Element | Trigger | Properties | Duration / easing |
|---|---|---|---|
| **Nav item** | hover | `background-color` → `color-mix(persona 6%, transparent)`; `color` → ink. No movement. | 160ms `--ease-inout` |
| Nav item | active route | already tinted; add 2px inset persona left-border that grows in width 0→2px on activate | `--m-base` |
| **Card** | hover | `box-shadow` lift (`0 16px 40px -24px` deeper) + `transform: translateY(-2px)`. Only on interactive/clickable cards. | `--m-base` `--ease-out` |
| Card | press (if clickable) | `translateY(0) scale(0.995)` | `--m-fast` `--ease-press` |
| **Pill / control** (month nav, "Monthly ▾", filters) | hover | `background` to `--fl-frame` tint, `border-color` darken | 140ms |
| Pill | press | `scale(0.96)` | `--m-fast` `--ease-press` |
| **Persona segmented control** | hover (inactive seg) | seg `color` muted→ink, dot `scale(1.15)` | 140ms |
| Persona seg | press | whole control `scale(0.98)` for the press frame | `--m-fast` |
| **KPI / big number** | — | no hover motion (numbers don't wiggle) | — |
| **Buttons** (shadcn) | hover/press | keep shadcn defaults but retune press to `scale(0.97)` `--ease-press` | `--m-fast` |
| **Alert/spending pills** | hover | very slight `background` opacity bump 12%→16% | 140ms |

Rules: pointer feedback never exceeds 2px translate or 4% scale. Use `:active` (CSS) for press, not JS, so it's instant and reduced-motion-safe.

**Reduced motion:** drop all translate/scale; keep the color/background changes (instant) so hover affordance still reads. Press feedback becomes a flat background change.

---

## 5. Loading / skeleton motion

`skeleton.tsx` currently uses `animate-pulse` (opacity loop). Upgrade to a **directional shimmer** that matches "frosted" glass, but keep pulse as the reduced-motion-safe base.

- **Skeleton shimmer:** a `linear-gradient(100deg, transparent 30%, var(--fl-line)/60 50%, transparent 70%)` swept via `background-position` (or a translating pseudo-element), 1400ms linear, infinite. Tint the sweep with `--persona` at ~8% so even loading feels persona-aware. Base block = `--fl-line`, radius matches the target (`--radius-card` for cards, `999px` for pills/bars).
- **Layout-matched skeletons:** each page provides a skeleton that mirrors its real grid (KPI strip = 4 blocks, chart = one tall block, table = N rows). No spinner anywhere — spinners read as "slow," skeletons read as "almost ready."
- **Content swap:** when data arrives, skeleton `opacity 1→0` (120ms) and real content runs its §1/§3 reveal. Don't pop.
- Overview currently shows a bare `"Loading…"` string — replace with the layout-matched skeleton so the count-up/draw-in has something to bloom from.

**Reduced motion:** no sweep, no pulse — a static `--fl-line` block. The swap to content is instant.

---

## 6. Investment priorities — where to spend effort

**Invest (hero moments):**
1. **Persona switch (§2)** — the accent morph + moving sidebar pill + chart recolor + Joint gradient cross-fade. This *is* the product's identity; it should feel liquid and considered. Worth the `@property` setup and the dual-layer Joint handling.
2. **Overview page-load (§1)** — specifically the KPI count-up + cash-flow draw-in + dot-matrix fill. First impression of the dashboard; the dot-matrix in particular is cheap charm.

**Keep subtle / cheap (do not over-design):**
- Route transitions (§3) — a near-invisible fade. Resist the urge to make these expressive.
- Hover/press (§4) — 2px and 4% ceilings, CSS only.
- Skeletons (§5) — one shared shimmer primitive, reused everywhere.

**Anti-goals (explicitly avoid — these read as "AI-generated maximalism"):** parallax, scroll-triggered reveals beyond the initial mount, springy bouncing cards, animated gradients in the background, page-slide transitions, character-staggered text, confetti, anything that loops in the user's peripheral vision while they read numbers. Restraint is the brief.

---

## 7. Implementation notes (no full code)

- Add motion tokens (§0.2) and the reduced-motion block (§0.4) to `index.css`; register `@property --persona` (§2).
- Build three small primitives: `<CountUp value>` (uses `motion`'s `useMotionValue`/`animate` + `useReducedMotion`), `<DrawPath d>` (SVG `stroke-dashoffset` via `useInView`), and a `<Reveal stagger>` wrapper for card entrances (CSS class + `style={{'--i': index}}` delay, no JS).
- Convert savings bars from `height` to `transform: scaleY` for GPU-cheap entrance; convert the persona pill background to a single translating indicator.
- Gate the §1 Overview orchestration behind a "first mount" flag so persona/month changes don't replay it.
- Keep `motion` imports confined to chart/number primitives; verify the bundle delta stays under ~35 KB gz.
