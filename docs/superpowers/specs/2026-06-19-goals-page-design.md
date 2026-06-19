# Plan 7 — Goals Page Design

> Page-level addendum to `2026-06-18-finance-ui-rewrite-design.md` (§4 IA, §7 API).
> Covers the **Goals** page + its backend router. Locked decisions below.

## Goal
Surface the existing goals schema as a first-class page: per-goal **savings progress**
(saved vs target), a pace hint (monthly amount needed to hit the target date),
persona-scoped, with inline "saved" editing, add, and delete. Reuses the engine's
`analytics.goal_progress`; adds a thin FastAPI router. No engine changes.

## Backend contract (new — `backend/api/goals.py`)
All delegate to existing engine functions.
- `GET /api/goals?person_id=` → `analytics.goal_progress(db.get_goals(pid_or_all))`.
  Each row: `{ id, person_id, name, target_amount, saved_amount, target_date, horizon,
  notes, percent, monthly_needed }`. `percent` = saved/target×100 (0 when target is 0);
  `monthly_needed` = remaining ÷ whole months until `target_date` (null when no date).
- `POST /api/goals` body `{ person_id?: int|null, name: str, target_amount: float,
  saved_amount?: float=0, target_date?: str|null, horizon?: str="short", notes?: str="" }`
  → `db.add_goal(...)`; returns `{ ok: true }`.
- `PATCH /api/goals/{goal_id}` body `{ saved_amount: float }` → `db.update_goal_saved`;
  returns `{ ok: true }`.
- `DELETE /api/goals/{goal_id}` → `db.delete_goal`; returns `{ ok: true }`.

## Persona mapping (locked)
`db.get_goals` takes `int` (one person), `None` (shared/household goals only), or `"all"`.
The persona switch sends `person_id` (int) or omits it (Joint):
- **You / Spouse** → `person_id` int → that person's goals.
- **Joint** → `person_id` omitted → router maps to `"all"` (everyone's + shared goals).
- A goal **added from Joint** (`person_id` omitted/null) is a shared/household goal;
  added from You/Spouse it belongs to that person. (matches `goals.person_id IS NULL`.)

## Frontend (`web/src/pages/Goals.tsx`, mutating like Budgets)
- Goal cards: name, optional `by {target_date}`, an inline numeric **saved** input
  (commit on blur → `updateGoalSaved`) over `/ {target}`, a progress bar
  (`--persona`, → `--pos` green when ≥100%), and a footer line: percent + pace hint
  (`{monthly_needed}/mo to stay on track`) or "reached 🎉".
- Add form (toggle): name, target amount, optional target date, horizon (short/long).
- Delete via a ✕ button (`aria-label="Remove {name} goal"`).
- After every mutation, refetch (`load()`), same as Budgets.
- Frosted Ledger: `--persona` accent; `--pos` for completed; tabular numerals; 18px cards.

## Out of scope
Goal editing beyond the saved amount (rename/retarget), per-person split views in Joint,
contributions ledger, linking goals to Net Worth accounts. (Future plans.)
