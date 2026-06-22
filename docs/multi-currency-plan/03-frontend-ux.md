# 03 — Multi-Currency Frontend UX Plan ("Frosted Ledger")

**Role:** Senior frontend/product designer (fintech). **Mode:** Planning only — no source changed.
**Date:** 2026-06-22. Paths are absolute under repo root `C:/Users/lahat/Documents/Claude/HomeFinance/`.

## Scope & premise
Add a **global display-currency toggle** between **ILS (₪)** and **USD ($)**. Every amount, KPI,
and chart re-expresses in the chosen currency. Each transaction carries an **original amount +
currency**; the backend (sibling agents' conversion engine) supplies a **converted value per
display currency using the transaction-date rate**. The frontend never does FX math — it only
*chooses which currency to render* and *surfaces the original where it matters*.

**Backend contract this plan assumes** (sibling plans 01/02). Each money-bearing record gains:
`original_amount: number`, `original_currency: "ILS" | "USD"`, and a converted field the UI reads
for the active display currency. Two viable shapes — pick one with the backend agents:
- **(A, preferred) Pre-converted map**: `converted: { ILS: number; USD: number }` per row + a
  `rate_missing?: boolean` flag. UI reads `converted[displayCurrency]`. Zero client FX, trivially
  correct, works for KPIs/charts the backend already aggregates.
- **(B) Server re-query**: every list/overview/networth endpoint accepts `?display=ILS|USD` and
  returns already-converted scalars plus per-row `original_amount`/`original_currency`. UI re-fetches
  on toggle.
This plan is written so the UI works under either; **(A) is preferred** because it makes the toggle
instant (no refetch) and keeps charts in sync for free. Where (B) is used, the toggle becomes a
query-param dependency in each page's existing `useEffect`.

---

## 1. Display-currency toggle

### 1.1 Where it lives
- **Primary control: top-bar pill cluster** (the shared page header from `ui-fix-plan` CC-5), a
  segmented `₪ ILS | $ USD` pill sitting beside the month stepper / theme toggle. Currency is a
  *viewing lens* like persona and theme — it belongs in global chrome, visible on every page, not
  buried in Settings. Modeled visually on the persona segmented switch in
  `web/src/components/app-sidebar.tsx` (recessed track, raised active pill).
- **Secondary mirror: Settings → Appearance/Money** sets the **default** currency (the value the
  app boots with) and is where FX-rate inspection lives (§3.7). The top-bar pill is the quick
  per-session switch; Settings is the persistent default.
- Until the shared top-bar exists, land the pill in `web/src/components/app-sidebar.tsx` next to the
  theme toggle so the feature ships without blocking on CC-5.

### 1.2 State: a `CurrencyProvider` context
New file **`web/src/lib/currency.tsx`**, modeled on `web/src/lib/theme.tsx` (cleaner localStorage
pattern than `persona.tsx`). Tiny signatures only:

```ts
export type Currency = "ILS" | "USD";
type CurrencyCtx = {
  currency: Currency;
  setCurrency: (c: Currency) => void;
  symbol: string;            // "₪" | "$"
  format: (n: number, opts?: { cents?: boolean; signed?: boolean }) => string;
};
export function CurrencyProvider({ children }: { children: React.ReactNode }): JSX.Element;
export function useCurrency(): CurrencyCtx;
```

- **Persistence:** `localStorage["hf-currency"]`, default `"ILS"` (Israeli household: @revera-ai.com,
  Ido/Aviv — the existing USD default in `money.tsx` is almost certainly wrong; see `ui-fix-plan/
  04-finance.md §3`). Default is overridable from Settings.
- **Propagation:** wrap in `web/src/App.tsx` *inside* `PersonaProvider` (so currency is available to
  every page). Set `document.documentElement.dataset.currency = currency` (mirrors the persona/theme
  effect) for any CSS hooks.
- **How it reaches every render:** `Money` (§2) calls `useCurrency()` internally, so **every existing
  `<Money>` re-expresses automatically** when the toggle flips — no per-call-site change for the
  common case. KPIs/charts that format via the bare `formatMoney(n)` helper migrate to the context's
  `format` (or a `useCurrency().format`) so they react too.

### 1.3 How it propagates to charts
- **Shape A:** charts already receive backend-aggregated series; switch the series accessor to
  `point.converted[currency]`. Axis tick labels and tooltips format via `useCurrency().format`.
  Re-render is instant (context change → React re-render), no refetch.
- **Shape B:** add `currency` to the dependency array of each page's data `useEffect` (Overview,
  NetWorth, Budgets, Transactions, Recurring, Goals) so the page re-fetches converted figures.
- Axis labels gain the active **symbol** (e.g. `₪2.4k` / `$640`); chart `aria-label`s include the
  currency word for screen readers.

---

## 2. `money.tsx` redesign

Current `web/src/components/money.tsx` is a single USD `Intl.NumberFormat` + `formatMoney(n)` +
`<Money value colored>`. Redesign keeps that surface backward-compatible and layers original-currency
awareness.

### 2.1 Props (tiny signatures)
```ts
type MoneyProps = {
  value: number;                 // amount already in DISPLAY currency (converted by backend)
  colored?: boolean;             // existing: green/red/neutral by sign
  cents?: boolean;               // default true in lists, false for headline KPIs
  original?: { amount: number; currency: Currency };  // the as-entered value
  rateMissing?: boolean;         // backend couldn't convert (see §4)
  emphasis?: "kpi" | "inline";   // type scale hook (40px/800 vs inline)
};
export function Money(props: MoneyProps): JSX.Element;
export function useMoneyFormat(): (n: number, currency: Currency, opts?) => string; // shared formatter
```

### 2.2 Formatting (₪ and $)
- Use `Intl.NumberFormat` per currency, **created once and memoized by currency** (not on every
  render): `new Intl.NumberFormat("en-US", { style: "currency", currency })` → `$` prefix, grouping.
  For ILS, `currency: "ILS"` yields `₪` with `en-US` (symbol-prefix, Latin digits — desirable; we do
  **not** want a `he-IL` RTL/Hebrew-digit treatment in this LTR app).
- **Symbol placement:** both `₪` and `$` are **leading** (`₪1,234.50`, `$1,234.50`) — consistent,
  ledger-aligned columns.
- **Decimals:** `cents:true` → 2 fraction digits (transaction lists, budget rows). `cents:false` →
  0 digits for headline KPIs / big numbers (`₪12,480`), matching `ui-fix-plan` whole-unit guidance.
- **Tabular figures:** keep `fontVariantNumeric:"tabular-nums"` (already global + inline); retain so
  digits align across the ledger.
- **Sign/color:** keep existing `colored` semantics via `--pos`/`--neg`; unchanged.

### 2.3 Surfacing the original currency (the heart of the feature)
When `original.currency !== displayCurrency`, the value was *entered in another currency and converted*.
Make that legible by surface, escalating in prominence:
- **Default (inline, lists): subtle marker + tooltip.** Render the converted value normally, then a
  small muted superscript/affordance (a dotted underline or a tiny `↺`/`≈` glyph in `--fl-muted`).
  On hover/focus a **tooltip** (`web/src/components/ui/tooltip.tsx`, already present) reads:
  `Originally ₪420 · converted at the May 3 rate`. This keeps tables uncluttered while honest.
- **Transactions table: a dedicated Original column** (§3.1) rather than a tooltip — the original is
  load-bearing there.
- **Headline KPIs / cards:** if a card mixes currencies (the normal case for aggregates) **no per-row
  original** is shown — instead the card header carries a `≈ converted to ₪` micro-label so the user
  knows the total is a conversion, not a native sum.
- **Badge variant** (`original` differs, compact contexts like chips): a tiny
  `web/src/components/ui/badge.tsx` showing the original currency code (`ILS`) in `--fl-muted`.
- When `original.currency === displayCurrency`, render plain — **no marker** (avoid noise; most rows
  in a single-currency household match the display currency).

---

## 3. Per-surface impact

### 3.1 Transactions — `web/src/pages/Transactions.tsx` (P0)
- Current `amount` column renders `<Money value colored>`. **Split into two columns:**
  - **Amount (display)** — converted value in the active currency, colored by sign (the existing
    right-aligned column). This is the sortable, primary column.
  - **Original** — `original_amount` + `original_currency` shown only when it differs from display
    (e.g. `₪420`); otherwise blank/muted dash so matching rows don't repeat themselves. Non-sortable,
    `--fl-muted`, smaller. Mockup-consistent with the existing muted Date column treatment.
- Extend the `Transaction` type in `web/src/lib/api.ts` with `original_amount`,
  `original_currency`, and `converted` (shape A) / display-converted `amount` (shape B).
- The transfer-pair strip (`openPairs`) `<Money value={p.amount}>` re-expresses via context for free.
- **Filter add (P2):** a currency facet in the filter bar (`All / ₪ entered / $ entered`) to find
  foreign-currency entries — reuses the existing `pill` select pattern.

### 3.2 Overview — `web/src/pages/Overview.tsx` (P0)
- KPI strip (`Income/Spending/Net/Savings rate`) + the planned five signature cards: all scalars come
  from `/overview` already converted to display currency (shape A: backend pre-converts the
  aggregate; shape B: refetch on currency change). `formatMoney(amount)` in the By-category list
  migrates to `useCurrency().format`.
- **Cash-flow & savings-rate charts:** series values switch to the converted accessor; **y-axis tick
  labels + tooltips** carry the active symbol. Because conversion is transaction-date based, mixed-
  currency months are already reconciled server-side — the chart just plots converted numbers.
- **Card header micro-label:** aggregates that blend currencies show a tiny `in ₪` tag in the card
  header (consistency with §2.3) so the toggle's effect is obvious.

### 3.3 Budgets — `web/src/pages/Budgets.tsx` (P1)
- `spent`, `budget`, `projected_eom` render via `<Money>` in display currency. **Caps are entered in
  the display currency**; the inline `<input type=number>` cap editor must show the active **symbol**
  as a prefix/adornment so a user toggled to USD doesn't accidentally type a shekel cap. The
  `PaceMeter` is ratio-based (`spent/budget`) — **currency-agnostic, no change**. Decision for backend:
  whether a budget cap is stored in a fixed currency or in the display currency at entry time
  (recommend: store cap currency alongside the amount; convert for display like transactions).

### 3.4 Net Worth — `web/src/pages/NetWorth.tsx` (P1)
- Summary `net/assets/liabilities`, the `delta`, reconciliation figures, and account-row balances all
  flow through `<Money>`/`formatMoney` → re-express on toggle. Account balances may be **held in
  different native currencies** (e.g. a USD brokerage in an ILS household) — the **account row should
  show the original currency** (badge per §2.3) alongside the converted balance, and the inline
  balance editor needs the symbol adornment for the *account's own* currency, not the display one.
- **Sparkline** `net` series switches to converted accessor; stroke/axis unchanged.
- Reconciliation "off by `formatMoney(discrepancy)`" re-expresses; note that **FX rounding** can make
  a converted reconciliation appear slightly off — show reconciliation in the **account's native
  currency** to avoid false discrepancies (important correctness note for the backend agents).

### 3.5 Import preview — `web/src/pages/Import.tsx` (P1)
- The review table currently hard-codes `$` (`{r.amount < 0 ? "−" : "+"}${Math.abs(r.amount)…}`).
  This must become **currency-aware on the row's *source* currency**, not the global display toggle —
  an imported ₪ statement should preview in ₪. Add `currency` to `ImportRow` (`web/src/lib/api.ts`)
  and a per-file/auto-detected source-currency selector beside the existing Source select
  (`auto/amazon/card/bank`). Show a small `detected: ₪ ILS` confidence note (parallels the existing
  Ollama-readiness line). The **commit** sends original amount + currency; conversion happens
  server-side at transaction date.
- Replace the hard-coded `POS`/`NEG` `$` literals with the shared formatter.

### 3.6 Other pages (P1/P2)
- **Recurring** (`Recurring.tsx`): committed total, typical/last amounts, anomaly price-change
  details → `<Money>` re-express; price-change `detail` strings that embed a currency must be built
  with the formatter, not literal `$`.
- **Goals** (`Goals.tsx`): `target_amount`, `saved_amount`, `monthly_needed` via `<Money>`; the
  add-goal target input gets the symbol adornment (stored in display currency at entry).
- **Events** (`Events.tsx`): event `total` via `<Money>`.

### 3.7 Settings — `web/src/pages/Settings.tsx` (P1)
- New **"Money / Appearance" section** (mockup uppercase `h2` label, `frosted-card`):
  - **Default display currency** — `₪ ILS / $ USD` segmented control writing the `CurrencyProvider`
    default (persisted to `localStorage` + optionally a backend pref).
  - **FX rates (inspect, P1; manage, P2):** since conversion is transaction-date based and
    server-managed, Settings should at minimum **inspect** the rate source — a read-only panel:
    "Rates: ECB/`<source>`, last refreshed `<date>`; range `<min>–<max>` ₪/$". If the backend lets
    users supply/override rates, add an editable rate table (date → ₪/$). Coordinate the exact
    capability with sibling plans 01/02; UI scaffolds read-only first.
- Keep within the existing `RuleSection`/card visual system.

---

## 4. States

- **Missing-rate fallback (`rateMissing`):** backend couldn't find a transaction-date rate. The UI
  must **never silently show a wrong/zero converted number.** Render the **original amount** with its
  native symbol plus a muted `(no rate)` / `≈?` affordance and a tooltip: *"No exchange rate for May 3
  — showing the original ₪ amount."* In aggregates, the card header flags `n rows not converted` so
  totals aren't trusted blindly. `--neg` is *not* used here (it's not an error of the user's making) —
  use `--fl-muted` + an info tone.
- **Ambiguous / unknown currency:** if `original_currency` is null/unknown, treat as missing-rate:
  show the raw number with a `?` currency badge and a tooltip prompting the user to set the source
  currency (links to the Import source selector / a row edit). Never assume USD.
- **Loading:** while a page fetches converted data (shape B refetch on toggle), reuse the planned
  skeleton shimmer (`web/src/components/ui/skeleton.tsx`, `ui-fix-plan` CC-8) in the money cells —
  do **not** flash stale-currency numbers. With shape A no loading state is needed (instant
  re-render). Toggling the pill should feel instant; if shape B introduces a refetch lag, optimistic-
  format the already-loaded original amounts with a subtle "updating…" dim until fresh values arrive.
- **Error (toggle/fetch fail):** distinguish from empty (`ui-fix-plan` CC-9) — keep the prior
  currency's numbers, surface a `sonner` toast ("Couldn't switch to USD — rates unavailable"), and
  revert the pill. Never leave the user looking at unconverted numbers labeled as the new currency.

---

## 5. Fit to Frosted Ledger & persona accents
- The currency pill reuses the **segmented-switch language** of the persona switch and the
  `pill`/`frosted-card` tokens — it must read as a sibling of the persona/theme controls, not a new
  visual idiom. Active segment = raised white pill; track = recessed `--fl-line`.
- **Original-currency markers stay in `--fl-muted`** — they're metadata, never persona- or
  semantic-colored, so they don't fight income/spend (`--pos`/`--neg`) or persona inks
  (`--persona-you`/`--persona-spouse`). The persona accent (`--persona`) continues to own bars,
  active nav, and KPI emphasis; currency adds no new accent color.
- Symbols and converted-from labels respect dark-mode tokens (route through `--fl-*`, never hard-code
  hex — same lint as `ui-fix-plan` CC-12).
- Tabular numerals + leading symbols keep columns ledger-aligned in both currencies.

---

## 6. Priority rollup (exact files)

**P0 — toggle live + transactions honest:**
- `web/src/lib/currency.tsx` (new `CurrencyProvider`, modeled on `theme.tsx`).
- `web/src/App.tsx` (wrap provider).
- `web/src/components/money.tsx` (currency-aware `Money` + shared formatter; original/tooltip; cents).
- `web/src/components/app-sidebar.tsx` (currency pill until top-bar exists).
- `web/src/lib/api.ts` (extend `Transaction` + chosen converted shape).
- `web/src/pages/Transactions.tsx` (Amount-display + Original columns).
- `web/src/pages/Overview.tsx` (KPIs/charts re-express; `formatMoney`→context).
- Update `web/src/components/money.test.tsx` (USD-only assertions will break; add ILS cases).

**P1 — every money surface + settings:**
- `web/src/pages/NetWorth.tsx`, `Budgets.tsx`, `Import.tsx` (source-currency, not display),
  `Recurring.tsx`, `Goals.tsx`, `Events.tsx`.
- `web/src/pages/Settings.tsx` (default currency + read-only FX inspect).
- Missing-rate / ambiguous / loading / error states in `Money` + pages.

**P2 — refinement:**
- Transactions currency filter facet; editable user FX rates in Settings (if backend supports);
  per-card "in ₪" micro-labels everywhere; symbol adornments on all amount inputs.

## 7. Open questions for backend agents (plans 01/02)
1. Converted shape **A (pre-converted map)** vs **B (display query-param)** — UI strongly prefers A.
2. Default app currency = **ILS** (recommended) — confirm.
3. Are **budget caps / goal targets / account balances** stored in a fixed currency, or in display
   currency at entry? (Drives input adornment + storage.)
4. FX source + whether users can **override** rates (drives Settings: inspect-only vs editable).
5. Reconciliation & account balances: show in **native** currency to avoid FX-rounding false
   discrepancies — confirm backend exposes native figures.
