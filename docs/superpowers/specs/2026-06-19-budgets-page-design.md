# Plan 5 — Budgets Page Design

> Page-level addendum to `2026-06-18-finance-ui-rewrite-design.md` (§4 IA, §7 API).
> Covers the **Budgets** page + its backend router. Locked decisions below.

## Goal
Surface the latent budgets schema as a first-class page: per-category **budget vs actual
for the current month**, pace-aware, persona-scoped, with inline cap editing, add, and
delete. Reuses the engine's `analytics.budget_status`; adds a thin FastAPI router.

## Backend contract (new — `backend/api/budgets.py`)
All three delegate to existing engine functions; no engine changes.
- `GET /api/budgets?person_id=` → `analytics.budget_status(db.get_transactions(pid),
  db.get_budgets(pid), parents)` where `parents = db.category_parents(pid)` for a real
  person and `{}` for Joint. Each row:
  `{ id, person_id, category, amount, budget, spent, expected_to_date, projected_eom,
  pct, status }`, `status ∈ {on_track, ahead, over}`, computed for the current calendar
  month (pro-rated to today). A budget on a parent name rolls up its children.
- `PUT /api/budgets` body `{ person_id?: int|null, category: str, amount: float }` →
  `db.set_budget`; returns `{ ok: true }`. Upsert (one cap per person+category).
- `DELETE /api/budgets/{id}` → `db.delete_budget`; returns `{ ok: true }`.
- Registered in `backend/main.py`; request body via `BudgetUpsert` in `backend/schemas.py`.

## Persona model (LOCKED — differs from Transactions)
Budgets are stored **per-person OR household** (`person_id IS NULL`), so:
- You → `person_id = people[0].id` (that person's budgets, their txns, their parents).
- Spouse → `person_id = people[1].id`.
- **Joint → `person_id = None`**: the **household budget set** (`get_budgets(None)`)
  compared against everyone's merged spend (`get_transactions(None)`). No parent rollup
  in Joint (categories are per-person → `parents = {}`). This is the chosen semantic.

## Frontend (`pages/Budgets.tsx`)
`lib/api.ts` gains `type Budget` + `getBudgets({personId})` / `setBudget({personId,
category, amount})` / `deleteBudget(id)`. The page lists one row per budgeted category.

### Visual (Frosted Ledger — frontend-design at build)
Signature = the **pace meter**: each row is a horizontal track; fill width = `spent/cap`,
and a thin vertical tick sits at `expected_to_date/cap` (where you *should* be today).
`status` drives color — `on_track` persona/neutral, `ahead` amber `#F59E0B`, `over` red
`--neg`. Big tabular cap & spent numbers via `<Money/>`. Inline-editable cap (number
input committing on blur → `setBudget`), an "add budget" row (free-text category +
amount), a delete affordance per row, and an empty state inviting the first budget.

## Out of scope (later plans)
Per-month historical budgets, a parent-budget creation UI, category management (Settings
plan owns categories — "add budget" takes a free-text category name), and bulk editing.

## Files
- `backend/api/budgets.py` (create), `backend/schemas.py` (+`BudgetUpsert`),
  `backend/main.py` (register router).
- `tests/api/test_budgets.py` (create).
- `web/src/lib/api.ts` (+`Budget`, 3 fns), `web/src/lib/api.test.ts` (+tests).
- `web/src/pages/Budgets.tsx` (create) + `web/src/pages/Budgets.test.tsx` (create).
- `web/src/routes.tsx` (swap `/budgets` placeholder).

## Testing (TDD)
- **Backend** (`tests/api/test_budgets.py`, temp-DB `client`/`people` fixtures): GET
  returns a row with `budget`/`spent`/`status` for a Groceries cap with a current-month
  txn (dated via `date.today()` so it's deterministic); PUT upserts a cap that then
  appears in GET; DELETE removes it.
- **Frontend** (Vitest): renders rows from mocked `getBudgets`; editing a cap calls
  `setBudget` with the new amount; clicking delete calls `deleteBudget(id)`.
- Existing engine tests for `budget_status` keep passing (untouched).

## Commits (≈4)
1. `feat(api): budgets router (status + upsert + delete)`
2. `feat(web): budgets API client`
3. `feat(web): Budgets page with pace meters + inline edit`
4. `feat(web): wire /budgets route`
