# HomeFinance UI/UX Audit — "Frosted Ledger" Gap Analysis

**Auditor role:** Senior UI/UX designer. **Mode:** Planning only (no source modified).
**Date:** 2026-06-22

## Sources of truth
- Locked visual design: `.superpowers/brainstorm/2658-1781817225/content/style-zentra.html`
- Parent spec: `docs/superpowers/specs/2026-06-18-finance-ui-rewrite-design.md`
- Per-page specs: `docs/superpowers/specs/2026-06-19-*.md`
- Tokens (already present, correct): `web/src/index.css` (`--fl-*`, `--persona-*`, `.frosted-card`, `--showpiece`)

## Verdict in one line
The data plumbing is done and correct; the **visual identity is almost entirely unbuilt.**
Tokens exist but components are plain inline-styled boxes. The app currently reads as a
generic admin table app, not the airy, branded "Frosted Ledger" in the mockup. The single
biggest miss is the **app shell** (frame, brand, sectioned nav, top bar) and the **five
signature Overview cards**, none of which exist. Persona labels still say "You/Spouse" and
must become **Ido/Aviv**.

---

## Cross-cutting findings (apply to every page)

### CC-1 (P0) — No app frame / shell
The mockup wraps everything in a rounded `--fl-frame` surface floating on a `--fl-canvas`
background, with a deep soft drop shadow (`box-shadow:0 24px 60px -34px`). Current
`routes.tsx::AppLayout` is a bare flexbox: sidebar + `<main padding:24>`. There is no frame,
no rounding, no shadow, no max-width centering. **Fix:** introduce a centered rounded frame
container (canvas → frame → sidebar+main), matching the mockup's `.frame`.

### CC-2 (P0) — Sidebar is missing its entire identity
`web/src/components/app-sidebar.tsx` is the highest-leverage file. The mockup sidebar has,
top to bottom: (1) **brand mark** — a 24px gradient-rounded square + "Household" wordmark;
(2) **segmented persona switch** with **colored dots** (blue/pink/conic gradient) inside a
recessed `#EEF0F3` track, active segment a white raised pill; (3) a **"Money" section
label** (tiny uppercase, `--soft`); (4) **nav with icons**, active item a **solid dark
ink pill with white text** (not a tinted persona wash); (5) a **divider**; (6) the
**"＋ Import" highlighted item** in persona-blue bold; (7) a **"🔒 Local only · nothing
leaves this device" footer** pinned to the bottom.
Current sidebar has **none** of: brand mark, dots, section label, icons, divider, lock
footer. The persona switch is plain pill buttons; nav active state is a persona tint, not
the dark ink pill. The theme toggle is a stray text button mid-sidebar (mockup has no such
control here — theme lives in the top bar). **Fix:** rebuild the sidebar to the mockup.

### CC-3 (P0) — Persona labels must be Ido / Aviv
`app-sidebar.tsx` `PERSONAS` and `lib/persona.tsx` fall back to "You"/"Spouse". The household
is **Ido (blue) / Aviv (pink) / Joint (gradient)**. Seed/display defaults must read
**Ido / Aviv**, with rename still available in Settings. Persona dots must carry the ink
colors. The fallback strings (`?? "You"`, `?? "Spouse"`) and the sidebar `text()` map are
the concrete edit points.

### CC-4 (P1) — Persona "Joint" accent never renders as a gradient
`lib/persona.tsx` only swaps `--persona` to blue or pink; for Joint it leaves blue (it never
sets the gradient). The mockup's whole thesis is **Joint = blue→pink**. Because `--persona`
is used as a flat `color`/`background` in many places (nav active, buttons, bars), a gradient
value will break those usages. **Fix:** decide a dual-token approach — keep a flat
`--persona` (solid, for text/!) **and** a `--persona-fill` (can be a gradient, for bars/
accents) so Joint reads as the gradient on fills while text stays legible.

### CC-5 (P1) — Top bar / page chrome missing everywhere
The mockup's main column opens with a **top bar**: gradient-clipped page title
("Overview · **Joint**"), then a cluster of **pill controls** (month stepper `◀ May 2026 ▶`,
"compared to Apr", granularity `Monthly ▾`, search `🔍`, and a gradient **avatar**). Plus a
**theme toggle**. Currently each page hand-rolls a bare `<h1>` + ad-hoc controls; titles are
not gradient-clipped for Joint, there is no global control cluster, no avatar, no search.
**Fix:** a shared page-header component (title with persona-gradient `<b>`, right-aligned
pill cluster, theme toggle, avatar).

### CC-6 (P1) — Typography & numerals under-applied
Spec demands **Plus Jakarta Sans**, big numbers at weight 800 with `-0.03em` tracking, and
tabular numerals. `index.css` sets the font + `tabular-nums` globally (good), but card
titles, KPI labels, and section headers don't consistently use the mockup's scale (13px/700
card titles, 10.5px/700 uppercase `--soft` labels, 40px big numbers). Many headers use
plain weights. **Fix:** a small type scale applied via shared components, not per-page
inline styles.

### CC-7 (P1) — Everything is inline-styled; no shared primitives
Every page redefines `pill`, `badge`, `h2`, card paddings inline. This guarantees drift from
the design and makes the fix hard to land consistently. The spec calls for shadcn primitives
(`card`, `badge`, `button`, `tabs`, `table`, `chart`, `skeleton`, `empty`, `sonner`). Only
`ui/table.tsx` and `money.tsx` exist. **Fix:** extract Frosted-Ledger primitives (Card,
CardHeader with the `···` affordance, Pill, Badge, SectionLabel, StatNumber, PaceBar) and
adopt shadcn where the spec names it. This is the enabling refactor for most P1 visual work.

### CC-8 (P1) — Loading & empty states are inconsistent / off-brand
Loading is a bare `"Loading…"` text on Overview/Recurring/NetWorth; Transactions/Budgets/
Goals show nothing while fetching. Spec calls for `@shadcn/skeleton` shimmer in card shapes
and `@shadcn/empty` for empties. Empty states exist as plain centered muted text on some
pages but are missing on Transactions (only a post-filter "no match") and have no
illustration/CTA hierarchy. **Fix:** skeleton cards on load; branded empty states with a
clear primary CTA.

### CC-9 (P1) — No error states anywhere
Every fetch `.catch()` silently degrades to `null`/`[]`, which then renders as a permanent
"Loading…" or an empty state. A failed API call is indistinguishable from "no data." **Fix:**
distinguish error from empty; show a retry affordance and a toast (`@shadcn/sonner`).

### CC-10 (P1) — Responsive / mobile not addressed
Layout uses a fixed 232px sidebar + flex main with no breakpoints; cards use fixed grids and
fixed-width inputs (e.g. `width:130`), and the Transactions table has no horizontal-scroll
guard at the page level. On a phone the sidebar will crowd content off-screen. **Fix:** the
sidebar should collapse to a top bar / drawer (`@shadcn/sheet`) below ~768px; card grids
should stack; the persona switch and pill clusters should wrap; tables get a scroll container.

### CC-11 (P1) — Keyboard focus & a11y gaps
- Persona switch uses `role="tab"`/`aria-selected` but isn't a real tablist (no arrow-key
  roving focus, no `tabpanel`), and the buttons have no visible focus ring tuned to the
  persona accent.
- Native checkboxes/`<input type=number>` are used raw; focus rings rely on UA defaults and
  won't match the `--persona` ring the spec wants.
- Sortable `TableHead`s are clickable `<th>`s with no `role`/`aria-sort` and aren't keyboard
  operable.
- Color is doing semantic work alone in several places (income vs spend, asset vs liability,
  budget status) — needs a non-color cue for color-blind users.
- The `details/summary` privacy disclosure on Insights is fine; most icon-only buttons (✕)
  do have `aria-label` (good).
**Fix:** real focus-visible rings on `--persona`; `aria-sort` on headers + keyboard sort;
ensure all interactive controls are reachable and labeled.

### CC-12 (P2) — Dark mode defined but unverified against brand
`.dark` token set exists in `index.css`, but inline-styled components hard-code several
colors (`#22C55E`, `#EF4444`, `#fff` text on persona buttons, `POS`/`NEG` consts in
Import/Insights). These won't adapt. **Fix:** route all colors through tokens so dark mode
holds together.

---

## Page-by-page gap analysis

### 1. Overview — `web/src/pages/Overview.tsx` (P0, the showcase)
**Demanded (mockup §5):** five signature cards in two rows. **Current:** a single flat KPI
strip + a generic "By category" bar list. This is the largest single gap. None of the five
signature cards exist. Detail:

- **(P0) Card 1 — Cash flow** (spans ~2/3 of row 1). Needs: In/Out/Net KPIs (green/ink/blue),
  a **hatched + gradient area chart** (the mockup uses an SVG `area` gradient fill plus a 45°
  `hatch` pattern and a `polyline` stroke), and an **"Ask AI" prompt strip** at the bottom
  (`Ask: what drove the spike in [eating out]…` with a gradient mark and a highlighted
  chip). Current Overview has no chart at all and no AI strip.
- **(P0) Card 2 — "This month"** (1/3 of row 1). Needs: a **40px big net number** + green
  delta pill (`▲ 15%`), then three labeled rows (Income green / Spending persona-blue /
  Saved purple) each with a value and a **mini progress bar**. Current shows only flat KPIs.
- **(P0) Card 3 — Savings rate** (row 2). Needs a **vertical pink bar chart** of recent
  months with the current month emphasized (darker pink gradient), an x-axis of month
  labels, and a rate badge in the header. Current shows a single percentage in the KPI strip.
- **(P0) Card 4 — "Who spent what" dot-matrix** (row 2, the Joint signature). Needs the
  **blue/pink dot grid** splitting spend between the two people + a legend with each person's
  total. Spec note: in single-persona view this becomes that person's category split (the
  current "By category" bars are the right fallback content but wrong placement/styling). The
  dot-matrix is the one module no single-user finance app has — it must be built.
- **(P0) Card 5 — AI Insights showpiece** (row 2). The one **glassy gradient** card
  (`--showpiece`), with a "✦ AI Insights" frosted tag, a big number, and a teaser sentence
  that **links to the Insights page**. Current Overview has nothing; the gradient currently
  only appears on the Insights page hero.
- **(P1) Top bar:** month stepper should be the **pill** stepper with the month label and a
  "compared to" pill and granularity pill; title should be gradient-clipped for Joint.
  Current is bare `‹ / ›` buttons.
- **(P1) Alerts:** the existing alert chips are good and on-brand (recurring "new subscription
  detected" surfaces here per spec) — keep, restyle to match pill system.
- **Responsive:** the two rows (`1.7fr/1fr` then `1fr/1fr/1.15fr`) must collapse to a single
  column on mobile.

### 2. Transactions — `web/src/pages/Transactions.tsx` (P1)
Functionally the most complete page (TanStack table, inline category edit, include toggle,
filter bar, transfer-pair detection, Joint person column with seam). Gaps are visual/polish:
- (P1) Filter bar uses raw `<input>`/`<select>` with inline `pill` style — should be the
  shared Pill/Select primitives; search should have a `🔍` affordance per the mockup chrome.
- (P1) Category editor is a bare `<input list=…>`; spec wants a combobox-feel; at minimum a
  consistent focus ring and chip styling.
- (P1) Header lacks the gradient title + global control cluster (CC-5). No month/source range
  filter (acknowledged out-of-scope in the page spec, fine).
- (P1) Empty state only appears **after** filtering ("No transactions match"); a true
  zero-data empty (no transactions imported yet) with an Import CTA is missing.
- (P1) No skeleton while loading; (P1) a11y on sortable headers (CC-11).
- The Joint left-seam (`inset 3px 0 0 personaColor`) and dot marker are a nice on-brand touch
  — keep.

### 3. Budgets — `web/src/pages/Budgets.tsx` (P1)
Logic is solid (pace meter with expected-to-date tick, status colors, projected EOM, inline
cap edit, add/remove). Gaps:
- (P1) Cards are plain `.frosted-card` rows — adopt shared CardHeader and the mockup's
  number scale; the `PaceMeter` is good but should use tokenized colors and a clearer legend
  for the "expected today" tick (currently an unlabeled dark line — needs a tooltip/legend,
  also a CC-11 color-only concern).
- (P1) Status uses `#F59E0B` hard-coded ("running hot") — tokenize.
- (P1) Header chrome (CC-5); skeleton/error states (CC-8/9).
- (P2) "ahead/running hot" semantics may confuse — copy review.

### 4. Recurring — `web/src/pages/Recurring.tsx` (P1)
Good content (committed total big number, fixed/variable split, anomaly chips, per-charge
confidence bar). Gaps:
- (P1) The summary "Committed each month" big number is the right idea but should match the
  mockup's 40px/800 treatment and sit in a proper signature card with a small sparkline or
  cadence visual.
- (P1) Anomaly chips use `borderColor:currentColor` inline — move to Badge primitive; the
  "maybe canceled" muted state needs a clearer affordance.
- (P1) Confidence is an 80px bar with only a `title` tooltip — add a visible label for a11y.
- (P1) Header chrome, skeleton/error (CC-5/8/9). Loading is a bare "Loading…".

### 5. Goals — `web/src/pages/Goals.tsx` (P1)
Clean (progress bar, percent, monthly-needed, target date, reached state, add/remove).
- (P1) Per the spec, **Joint unlocks side-by-side goal progress** between the two people —
  not implemented; goals are a flat list regardless of persona. Add the comparative Joint view.
- (P1) Card styling → shared primitives; the 🎉 "reached" state is charming, keep but
  consider a subtle success treatment beyond color (CC-11).
- (P1) Header chrome, skeleton/empty/error. Add form uses raw inputs.

### 6. Net Worth — `web/src/pages/NetWorth.tsx` (P1)
Strong (assets/liabilities summary, delta-since-snapshot, custom sparkline, statement
reconciliation card, account rows with asset/liability badges).
- (P1) Sparkline is a bare polyline — bring it toward the mockup's chart language (area
  gradient, axis, current-point marker) and tokenize the stroke.
- (P1) Per spec, **Joint shows per-person net-worth contribution** — currently one merged
  view; add the two-ink split.
- (P1) `#22C55E`/`#EF4444` hard-coded in reconciliation — tokenize; reconciliation "off by"
  state should be a proper alert.
- (P1) Header chrome, skeleton/error (CC-5/8/9).

### 7. Events — `web/src/pages/Events.tsx` (P1)
Note: Events is a real route but is **not** in the locked sidebar IA (mockup nav lists
Overview, Transactions, Budgets, Recurring, Goals, Net Worth, Import, AI Insights, Settings —
no Events). **Decision needed:** either (a) add Events to the sidebar IA intentionally with
an icon and section placement, or (b) fold it under another page. Today it's wired in
`routes.tsx` and the sidebar but absent from the design — an IA inconsistency to resolve.
- (P1) The inline tag-transactions editor is a long checkbox list inside the card — works but
  is dense; consider a dialog/drawer (`@shadcn/sheet`) per the import-wizard pattern.
- (P1) Card/badge styling → primitives; header chrome; empty state exists (good).

### 8. Import — `web/src/pages/Import.tsx` (P1)
Has a 3-step stepper (Drop file → Review → Done), Ollama 🟢/🔴 readiness, parse/commit,
inline row edit, already-imported guard, Joint-blocked guard. This is close to the spec's
wizard intent. Gaps:
- (P1) Step 1 is a plain `<input type=file>` — spec wants **drag-and-drop** with a dashed
  drop zone (`@shadcn/dialog`/`drawer`), and an auto-detect/confidence note + "learn a new
  format" path. Current has source select but no detected-mapping/confidence UI.
- (P1) Review table is a raw `<table>` with inline cell styles — should reuse the
  Transactions table primitive; amounts already colored (good).
- (P1) No progress streaming during agent parse (spec mentions SSE/polling) — currently a
  single "Reading…" busy flag. Acceptable for v1 but note the gap.
- (P1) The "＋ Import" sidebar item must be the **highlighted/accented** nav item (CC-2).
- (P1) Header chrome; the Joint-blocked message is good but should be a branded empty/notice.

### 9. AI Insights — `web/src/pages/Insights.tsx` (P1)
This is the **best-aligned page** — it correctly uses the `--showpiece` gradient hero, the
privacy disclosure (`details` "See exactly what's sent"), the API-key gate, and the
anonymized-aggregate framing. Keep the model. Gaps:
- (P1) The generate button and result card should use shared primitives; result formatting is
  plain `pre-wrap` text — could be structured.
- (P1) The Overview teaser (signature card 5) must **link here** — that link is the missing
  half of this surface.
- (P2) Loading is a button label flip ("Thinking…") — consider a spinner/skeleton.
- (P2) No error state if `generate` fails (CC-9).

### 10. Settings — `web/src/pages/Settings.tsx` (P1)
Covers people-rename, category rules, vendor groups (matches spec §4 "Settings absorbs
Categories, vendor groups, rename people, privacy info"). Gaps:
- (P1) **Privacy info** ("🔒 Local only / nothing leaves this device") is part of the spec for
  this page and the sidebar footer — currently absent here.
- (P1) People rename should show each person's **persona ink swatch** (Ido blue / Aviv pink)
  so the rename ties to the color identity; the "Editing rules for" person buttons reuse the
  persona pill but always paint `--persona` (active page accent), not the **selected person's
  own color** — should reflect per-person ink.
- (P1) Dense rule rows → primitives, section cards with the mockup's uppercase labels.
- (P1) Header chrome; the page has no theme/appearance or about section the chrome implies.

---

## Priority rollup

**P0 (identity-defining; do first):**
- CC-1 App frame/shell
- CC-2 Sidebar rebuild (brand, dots, section label, icons, dark-ink active pill, Import
  highlight, lock footer)
- CC-3 Ido/Aviv persona labels
- Overview signature cards 1–5 (cash-flow hatched chart, This-month bars, savings-rate bars,
  who-spent-what dot-matrix, AI-insights showpiece)

**P1 (brings each page up to the design language):**
- CC-4 Joint gradient accent · CC-5 shared top bar/chrome · CC-6 type scale · CC-7 shared
  primitives + shadcn adoption · CC-8 skeleton/empty · CC-9 error states · CC-10 responsive ·
  CC-11 a11y/focus
- Per-page P1 items above (Transactions polish, Budgets/Recurring/Goals/NetWorth styling +
  Joint comparative views for Goals & NetWorth, Import drag-drop, Insights linking, Settings
  privacy + per-person ink, Events IA decision)

**P2 (refinement):**
- CC-12 dark-mode token routing · copy review (Budgets status wording) · Insights loading
  polish · Events drawer pattern.

## Recommended sequencing
1. **Enabling refactor:** extract Frosted-Ledger primitives + adopt named shadcn components
   (CC-7), and split `--persona` / `--persona-fill` (CC-4). Nothing else lands cleanly first.
2. **Shell:** frame + sidebar + top bar (CC-1/2/5) and Ido/Aviv (CC-3).
3. **Overview five cards** — the showpiece, where the design earns its keep.
4. **Page sweep:** apply primitives + states + responsive + a11y to the remaining nine pages,
   adding the Joint comparative views and Import drag-drop along the way.
