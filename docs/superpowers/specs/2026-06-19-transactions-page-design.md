# Plan 4 — Transactions Page Design

> Page-level addendum to the parent spec `2026-06-18-finance-ui-rewrite-design.md`
> (§4 IA, §7 API surface, §8 component map). Covers only the **Transactions** page
> (Wave 3 "page-by-page", first page). Locked decisions below.

## Goal
Replace the `/transactions` `PagePlaceholder` with the full ledger: a Frosted-Ledger
data table of the active persona's transactions, with inline category editing, a
per-row include/exclude toggle, a filter bar, and column sort — all wired to the live
backend that Wave 1 already shipped. No engine or backend changes.

## Backend contract (already built — do not modify)
- `GET /api/transactions?person_id=` → list of rows. `person_id` omitted ⇒ Joint (all
  people). Each row: `{ id, person_id, date "YYYY-MM-DD", description, amount (− = spend,
  + = income), category, source, included (0|1), balance (number|null), person (name) }`.
- `PATCH /api/transactions/{id}` body `{ category?: string, included?: boolean }` → the
  updated row. 404 if the id is unknown.
- The query param is `person_id` (consistent with `getOverview`), **not** `persona`;
  the spec §7 table's `?persona=` is loose shorthand.

## Locked decisions
1. **Table = shadcn `table` + `@tanstack/react-table`** composed per the spec's
   data-table pattern (user choice, overriding a leaner plain-table option). Adds two
   deps: `@tanstack/react-table` (npm) and the shadcn `table` primitive (CLI `--yes`,
   non-interactive). Columns: Date · Description · Person *(Joint view only)* · Category
   *(inline edit)* · Amount *(`<Money colored>`)* · Included *(toggle)*. TanStack owns
   sorting (Date, Amount) and filtering.
2. **Category editor = inline `<datalist>`-backed text input**, options seeded from the
   distinct categories present in the loaded rows. No `/api/categories` endpoint is built
   here (the parent spec defers Categories to the Settings plan); free-text is allowed
   since `PATCH` accepts any string, so new category names still work.
3. **Filter bar (lean):** description search (case-insensitive substring, TanStack global
   filter) · category select (All / each present category) · include-state (All /
   Included / Excluded). Sort via header click on Date & Amount.
4. **Writes:** call `PATCH`, then replace the local row with the response (no full
   refetch). Include toggle uses a `switch`; excluded rows render muted.
5. **Persona scope:** fetch with `usePersona().personId`; switching persona refetches.
   Joint shows the Person column; single-persona hides it.

## Out of scope (later plans / Plan 10 parity)
Add/delete transactions (Import owns adds), bulk edit, source & month-range filters,
pagination/virtualization, the old Analysis charts.

## Data flow / files
- `web/src/lib/api.ts` — add `type Transaction`, `getTransactions({ personId })`,
  `updateTransaction(id, { category?, included? })` (reuse `apiGet` / `apiSend`).
- `web/src/components/ui/table.tsx` — shadcn table primitive (added via CLI).
- `web/src/pages/Transactions.tsx` — fetch + filter/sort state + the data table.
- `web/src/routes.tsx` — replace the `/transactions` placeholder with `<Transactions/>`.

## Visual (Frosted Ledger — frontend-design skill applied at build)
Frosted-card container; tabular-nums amounts via `<Money colored>` (income `--pos`
green, spend `--neg` red); persona accent (`--persona`) on the active sort header and
focus rings; muted styling for `included=0` rows; soft 18px card, generous row height.

## Testing (TDD, Vitest + Testing Library)
- `lib/api.test.ts` — `getTransactions` builds `/api/transactions?person_id=1` and omits
  the param for Joint; `updateTransaction` issues the `PATCH` with the right body.
- `pages/Transactions.test.tsx` — renders rows from a mocked `getTransactions`; the
  search box narrows visible rows; editing a category calls `updateTransaction`; toggling
  Included calls it with `{ included: false }`.
- Existing backend API tests already cover the endpoints; no engine changes.

## Commits (≈3)
1. `feat(web): transactions API client (list + update)`
2. `feat(web): Transactions data table (TanStack) with inline edit + filters`
3. `feat(web): wire /transactions route to the ledger page`
