# 04 — Finance UX & Data-Viz Fix Plan (Overview "Frosted Ledger")

Scope: persona rename (You→Ido, Spouse→Aviv), data-viz correctness for the
Overview signature cards, and financial UX conventions for a two-person household.
Planning only — no code changed. File paths are absolute-relative to repo root
`C:/Users/lahat/Documents/Claude/HomeFinance/`.

---

## 1. Persona rename: "You"→"Ido", "Spouse"→"Aviv"

### Where the two names actually come from
The names live in the SQLite `people` table and are **seeded once** in
`modules/database.py` → `init_db()` (lines ~186-188):

```python
for name in ("You", "Spouse"):
    c.execute("INSERT OR IGNORE INTO people(name) VALUES (?)", (name,))
```

- `INSERT OR IGNORE` only seeds when empty; it never re-runs once rows exist.
- Live DB (`data/finance.db`) already holds `(1,'You'), (2,'Spouse')`.
- API surfaces them verbatim: `backend/api/people.py` → `GET /people` → `db.list_people()`.
- Frontend consumes via `web/src/lib/api.ts` `getPeople()` and shows them through
  the `usePersona()` context (`web/src/lib/persona.tsx`) and the persona tabs
  (`web/src/components/app-sidebar.tsx`). Both files contain **hard-coded
  fallbacks** `"You"` / `"Spouse"` used only until `/people` resolves.
- The persona **keys** are the literals `"you" | "spouse" | "joint"`
  (`PersonaKey` in `persona.tsx`). These are internal identifiers, **not display
  labels** — do NOT rename the keys (touches routing/state); only change display.

### Cleanest end-to-end change (DB is source of truth)
The display names should come from the DB, not from frontend literals. Three
coordinated edits, **P0**:

1. **DB seed** — `modules/database.py` line 187: change the seed tuple to
   `("Ido", "Aviv")`. This fixes fresh installs.
2. **One-time data migration for the existing DB** — the live `data/finance.db`
   already has `You`/`Spouse`, and the seed won't overwrite them. Add a tiny
   idempotent rename in `init_db()` after the seed loop (uses the existing
   `db.rename_person` path / a direct UPDATE), e.g.:
   ```python
   c.execute("UPDATE people SET name='Ido'  WHERE name='You'")
   c.execute("UPDATE people SET name='Aviv' WHERE name='Spouse'")
   ```
   Person rows are keyed by `id`, and all transactions/budgets/goals reference
   `person_id`, so renaming is data-safe (already proven by
   `tests/test_rename_person.py::test_rename_keeps_data_linked_by_id`).
3. **Frontend fallbacks** — update the placeholder literals so the UI reads
   correctly before `/people` loads and keeps blue=Ido / pink=Aviv:
   - `web/src/lib/persona.tsx` line ~40: fallback `"You"`→`"Ido"`, `"Spouse"`→`"Aviv"`.
   - `web/src/components/app-sidebar.tsx`: `PERSONAS` array (lines 18-22)
     `text: "You"`→`"Ido"`, `"Spouse"`→`"Aviv"`; and the `text()` fallback
     (line 28) `"You"`→`"Ido"`, `"Spouse"`→`"Aviv"`.

### Color binding (keep blue=Ido, pink=Aviv) — already correct
`web/src/index.css`: `--persona-you: #3B82F6` (blue), `--persona-spouse: #EC4899`
(pink). `persona.tsx` maps `you→--persona-you`, `spouse→--persona-spouse`. Since
people[0]=Ido and people[1]=Aviv (seed order / ids 1,2), **blue=Ido, pink=Aviv
holds with no CSS change.** Leave the CSS var names as-is (renaming them is pure
churn touching every page).

### Test fixtures that reference "You"/"Spouse" (must update with the rename)
- `tests/api/conftest.py` — comment + fixture (`seeds "You"/"Spouse"`).
- `tests/test_rename_person.py` — `fresh_db["You"]`, asserts on seeded names.
- `tests/api/test_people.py` — `assert {p["name"]...} == {"You","Spouse"}`,
  comment `# "Spouse"`.
- `tests/api/test_insights.py`, `tests/test_budgets_parents_db.py`,
  `tests/test_networth.py`, `tests/test_events.py` — grep these for `"You"`/
  `"Spouse"` and update any seeded-name assertions.
- `web/src/pages/Insights.test.tsx` — check mocked person names.
Recommendation: update assertions to `{"Ido","Aviv"}`. **P0** (tests will fail otherwise).

---

## 2. Data-viz correctness — does the backend feed each signature card?

The locked design (`style-zentra.html`) shows these signature widgets: **Cash
flow in/out/net + hatched chart**, **This-month income/spending/saved**,
**Savings-rate trend**, **"Who spent what" split between the two people**, and
**AI Insights**. Current `GET /overview` (`backend/api/overview.py`) returns only
a single-month snapshot: `{month, months[], income, spend, net, savings_rate,
complete, by_category, alerts}`. `web/src/pages/Overview.tsx` renders just 4 KPIs
+ a by-category bar list — it does **not** implement the signature cards yet.

Gap analysis per card (the analytics already exist; the **endpoint doesn't expose them**):

| Design card | Data needed | Backend status | Gap |
|---|---|---|---|
| This-month income / spending / **saved** | scalar income, spend, net(saved) for selected month | ✅ returned by `/overview` | None. (Map `net`→"Saved".) **P0 wire-up only** |
| Cash flow in/out/net + hatched chart | per-month series `{month, income, spend, net, cumulative}` | ✅ `analytics.cash_flow()` exists (analytics.py L278) but **not exposed by any router** | **P1: expose series.** Add `series` (or a `/overview/cashflow` route) |
| Savings-rate **trend** | savings_rate per month across `months[]` | ⚠️ `/overview` returns only the selected month's rate; per-month rates exist in `monthly_savings()` but are collapsed to one value | **P1: return per-month `savings_rate` array** (already computed in the `recs` loop — just emit it) |
| "Who spent what" (per-person split / dot-matrix) | per-person spend, ideally per-category | ✅ `analytics.user_overlap(txns, a, b)` exists (analytics.py L826) — `{category, a_spend, b_spend, shared, diff, combined}` — **not exposed** | **P1: expose split.** Only meaningful in Joint view |
| AI Insights | insight text/preview | ✅ `/insights/preview` + `/insights/generate` exist (`api.ts`) | None (separate page; optional teaser card) |
| Spending alerts | flagged categories | ✅ `/overview.alerts` | None |

### Recommended endpoint changes (minimal, additive — won't break current UI)
- **Enrich `GET /overview`** (`backend/api/overview.py`) to add:
  - `series`: list of `{month, income, spend, net, savings_rate, complete}` for
    all `months` (build from the `recs` dict already in scope — near-zero cost).
    Feeds both the cash-flow chart and the savings-rate trend.
  - When `person_id is None` (Joint), add `split`: result of
    `analytics.user_overlap(txns, people[0].id, people[1].id)` for the
    "Who spent what" card. (Single-person views: omit or empty.)
- Add the new fields to the `Overview` type in `web/src/lib/api.ts`
  (`series: {...}[]`, `split?: {...}[]`) so the frontend is typed.
- Tiny signatures only:
  ```python
  # overview.py response additions
  "series": [{ "month": m, "income": .., "spend": .., "net": .., "savings_rate": .., "complete": .. }],
  "split":  [{ "category": str, "a_spend": float, "b_spend": float, "shared": bool, "diff": float, "combined": float }],
  ```
- **Frontend P1**: build the three chart cards in `Overview.tsx` (cash-flow
  in/out/net bars, savings-rate sparkline/trend, per-person split / dot-matrix).
  Use `--persona-you`/`--persona-spouse` for the two people in the split.

**Caveat — partial months:** `monthly_savings()` flags `complete`. The first and
last months are usually partial (statement cycles). Trend/cash-flow charts should
visually de-emphasize `complete:false` months (hatching/lighter fill — the design
already shows a hatched treatment) and headline scalars should default to the
`latest_complete_month` (the endpoint already does this for the selected month).

---

## 3. Financial UX conventions (a couple managing money together)

### Sign & color semantics (CSS already defines the palette in `index.css`)
- `--pos #22C55E` (green) = income / positive net.
- `--neg #EF4444` (red) = overspend / negative net / over-budget.
- `--saved #A855F7` (purple) = the "saved" series (net surplus) — **use this for
  the Saved KPI and the savings-rate trend**, distinct from green income.
- `--persona-you #3B82F6` (blue=Ido), `--persona-spouse #EC4899` (pink=Aviv) —
  for per-person split bars/dots only; never for income/spend semantics.
- **Net colored by sign**: `web/src/components/money.tsx` `<Money colored>`
  already does green-if-positive / red-if-negative / neutral-if-zero. Keep it for
  Net. **Fix:** the "Saved" figure should read purple, not green — today
  `Overview.tsx` renders Net with `colored` (green/red) and Saved isn't a distinct
  card. When the Saved card lands, color it `--saved`.
- **Spending alerts** (`Overview.tsx` L46-47) hard-code `#EF4444`/`#22C55E` and
  invert (up=red, down=green) — correct for spend semantics, but replace literals
  with `var(--neg)`/`var(--pos)` for consistency. **P2.**

### Money formatting / rounding / currency
- `web/src/components/money.tsx` uses `Intl.NumberFormat("en-US", currency:"USD")`
  → 2 decimals, `$`. **Currency caveat:** this is an Israeli household
  (emails @revera-ai.com, names Ido/Aviv); confirm whether USD is intended or it
  should be **ILS (₪)**. If ILS, change the formatter locale/currency once here —
  it's the single source of truth. **P1 decision needed.**
- KPI tiles: prefer whole-shekel/dollar rounding (no cents) for headline figures
  to reduce noise; keep cents in transaction lists. (Optional `compact`/`cents`
  prop on `Money`.) **P2.**
- **Tabular figures**: already applied (`fontVariantNumeric: "tabular-nums"`) in
  `money.tsx` and the category list. Ensure every numeric column/KPI uses it so
  digits align. ✅ mostly done.
- Savings rate shown as `Math.round(rate*100)%` — fine; show `—` when income is 0
  (`savings_rate` is `null`, already handled).

### Joint vs single-person aggregation
- `person_id` param drives scope: omitted = **Joint** (all rows), set = one person
  (`db.get_transactions(person_id)`). Joint is a true union of both ledgers, so
  income/spend/net/savings-rate aggregate correctly for free.
- The **"Who spent what" split is Joint-only** — show it only when
  `persona === "joint"`; in single-person view show that person's category
  breakdown instead. The persona tabs (`app-sidebar.tsx`) already gate this.
- **Transfers between the two people** can double-count in Joint (money leaving
  Ido and arriving at Aviv). Transfer detection exists
  (`/transactions/transfers`, `analytics.find_transfer_pairs`, `cross_person`
  flag) — Joint headline figures should net out cross-person transfers so a
  partner-to-partner move isn't read as spend+income. **P1 correctness item** for
  the Joint Overview (verify whether `_split`/`included` already excludes them).

### Genuinely useful to a two-person household
- Per-person contribution to savings (who saved more this month) — derivable from
  `series` filtered by `person_id`. **P2.**
- "Fair share" / who-paid-for-shared view via `user_overlap.shared` categories —
  surfaces mutual spending. **P2.**
- Month stepper already present; keep defaulting to latest **complete** month.

---

## 4. Priorities (exact files / endpoints)

**P0 — names correct end-to-end (no data-viz risk):**
- `modules/database.py` init_db seed → `("Ido","Aviv")` + idempotent UPDATE for
  existing `data/finance.db`.
- `web/src/lib/persona.tsx` (L40 fallbacks), `web/src/components/app-sidebar.tsx`
  (PERSONAS L18-22, text() L28).
- Update name assertions in `tests/api/test_people.py`,
  `tests/test_rename_person.py`, `tests/api/conftest.py` (+ grep other test files).
- Wire existing `net` → "Saved" KPI label in `Overview.tsx`.

**P1 — make the signature cards real:**
- `backend/api/overview.py`: add `series[]` (per-month income/spend/net/
  savings_rate/complete) and `split[]` (Joint only, via `analytics.user_overlap`).
- `web/src/lib/api.ts`: extend `Overview` type.
- `web/src/pages/Overview.tsx`: build cash-flow, savings-rate trend, who-spent-what
  cards; color Saved with `--saved`.
- Currency decision: USD vs **ILS** in `web/src/components/money.tsx`.
- Joint transfer-netting correctness check (`find_transfer_pairs`/`cross_person`).

**P2 — polish:**
- Replace hard-coded alert colors with `var(--neg)`/`var(--pos)` in `Overview.tsx`.
- Whole-unit rounding for headline KPIs; per-person savings & fair-share views.
