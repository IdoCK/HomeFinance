# UI Rewrite — Plan 7: Goals Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `/goals` placeholder with a persona-scoped page that shows savings-goal progress (saved vs target, pace hint), with inline saved-amount editing, add, and delete — backed by a new thin FastAPI goals router over the engine's goal functions.

**Architecture:** `backend/api/goals.py` delegates to `db.get_goals`/`add_goal`/`update_goal_saved`/`delete_goal` and `analytics.goal_progress`. `lib/api.ts` gains `Goal` + `getGoals`/`addGoal`/`updateGoalSaved`/`deleteGoal`. `pages/Goals.tsx` mirrors the Budgets page (cards + inline edit + add form), refetching after each mutation.

**Tech Stack:** FastAPI + pytest (TestClient, temp-DB fixtures); React 18 + TS, Vitest + Testing Library.

## Working Context
- Worktree `.claude/worktrees/ui-rewrite`, branch `feature/ui-rewrite`. Depends on Plans 1–6.
- **npm/npx via PowerShell**, prepending the portable Node to PATH first:
  `$env:Path = "C:\Users\lahat\node\node-v24.16.0-win-x64;" + $env:Path` (Node is not on PATH otherwise). Then `npm --prefix web ...` from the worktree root.
- **pytest via** `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest ...` from the worktree root.
- Design doc: `docs/superpowers/specs/2026-06-19-goals-page-design.md`.
- Engine (do NOT modify): `db.get_goals(person_id="all")` (int | None | "all"); `db.add_goal(person_id, name, target_amount, saved_amount, target_date, horizon, notes)`; `db.update_goal_saved(goal_id, saved_amount)`; `db.delete_goal(goal_id)`; `analytics.goal_progress(goals)` → each goal dict + `percent` (saved/target×100) + `monthly_needed` (remaining ÷ whole months to `target_date`, or null).

## Global Constraints (carried from the spec)
- Local-only; reuse the engine; do NOT modify `modules/*.py`. (spec §1)
- **Persona mapping:** You→people[0], Spouse→people[1] → that person's goals; Joint (`person_id` omitted) → router maps to `"all"`. Goal added from Joint → `person_id` null (shared). (design §Persona)
- Frosted Ledger: `--persona` accent, `--pos` green for completed goals, tabular numerals, soft 18px cards. (spec §3)

## File Structure (this plan)
```
backend/schemas.py              # MODIFY: + GoalCreate, GoalSavedUpdate
backend/api/goals.py            # CREATE: GET/POST/PATCH/DELETE goals
backend/main.py                 # MODIFY: register goals router
tests/api/test_goals.py         # CREATE
web/src/lib/api.ts              # MODIFY: + Goal type + 4 functions
web/src/lib/api.test.ts         # MODIFY: + 4 tests
web/src/pages/Goals.tsx         # CREATE
web/src/pages/Goals.test.tsx    # CREATE
web/src/routes.tsx              # MODIFY: /goals -> <Goals/>
```

---

### Task 1: Goals API router (backend)

**Files:**
- Modify: `backend/schemas.py`, `backend/main.py`
- Create: `backend/api/goals.py`, `tests/api/test_goals.py`

**Interfaces:**
- Consumes: `db.get_goals/add_goal/update_goal_saved/delete_goal`, `analytics.goal_progress`.
- Produces: `GET /api/goals?person_id=` → list of progress rows; `POST /api/goals`; `PATCH /api/goals/{id}`; `DELETE /api/goals/{id}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_goals.py`:
```python
def test_goals_returns_progress(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.add_goal(you, "Emergency fund", 10000.0, 2500.0, "2026-12-31", "short", "")

    r = client.get("/api/goals", params={"person_id": you})
    assert r.status_code == 200
    g = r.json()[0]
    assert g["name"] == "Emergency fund"
    assert g["percent"] == 25.0
    assert g["monthly_needed"] is not None


def test_add_goal_creates_row(client, people):
    you = people[0]["id"]
    r = client.post("/api/goals", json={"person_id": you, "name": "Car", "target_amount": 20000})
    assert r.status_code == 200
    goals = client.get("/api/goals", params={"person_id": you}).json()
    assert any(g["name"] == "Car" and g["saved_amount"] == 0 for g in goals)


def test_update_saved_recomputes_percent(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.add_goal(you, "Vacation", 5000.0, 0.0, None, "short", "")
    gid = client.get("/api/goals", params={"person_id": you}).json()[0]["id"]

    r = client.patch(f"/api/goals/{gid}", json={"saved_amount": 1500})
    assert r.status_code == 200
    g = client.get("/api/goals", params={"person_id": you}).json()[0]
    assert g["saved_amount"] == 1500
    assert g["percent"] == 30.0


def test_delete_goal(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.add_goal(you, "Temp", 100.0, 0.0, None, "short", "")
    gid = client.get("/api/goals", params={"person_id": you}).json()[0]["id"]

    client.delete(f"/api/goals/{gid}")
    assert client.get("/api/goals", params={"person_id": you}).json() == []


def test_joint_returns_all_goals(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.add_goal(you, "Mine", 100.0, 0.0, None, "short", "")
    db.add_goal(None, "Shared", 200.0, 0.0, None, "long", "")

    names = {g["name"] for g in client.get("/api/goals").json()}  # no person_id -> Joint -> all
    assert {"Mine", "Shared"} <= names
```

- [ ] **Step 2: Run it (fails — no route)**

Run: `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api/test_goals.py -q`
Expected: FAIL (404 — `/api/goals` not registered).

- [ ] **Step 3: Add the schemas**

In `backend/schemas.py`, append:
```python
class GoalCreate(BaseModel):
    person_id: Optional[int] = None
    name: str
    target_amount: float
    saved_amount: float = 0
    target_date: Optional[str] = None
    horizon: str = "short"
    notes: str = ""


class GoalSavedUpdate(BaseModel):
    saved_amount: float
```

- [ ] **Step 4: Create the router**

Create `backend/api/goals.py`:
```python
from typing import Optional

from fastapi import APIRouter

from modules import database as db
from modules import analytics
from backend.schemas import GoalCreate, GoalSavedUpdate

router = APIRouter(prefix="/goals", tags=["goals"])


@router.get("")
def list_goals(person_id: Optional[int] = None):
    """person_id omitted -> Joint -> all goals (everyone's + shared)."""
    goals = db.get_goals(person_id if person_id is not None else "all")
    return analytics.goal_progress(goals)


@router.post("")
def create_goal(body: GoalCreate):
    db.add_goal(body.person_id, body.name, body.target_amount, body.saved_amount,
                body.target_date, body.horizon, body.notes)
    return {"ok": True}


@router.patch("/{goal_id}")
def update_goal(goal_id: int, body: GoalSavedUpdate):
    db.update_goal_saved(goal_id, body.saved_amount)
    return {"ok": True}


@router.delete("/{goal_id}")
def remove_goal(goal_id: int):
    db.delete_goal(goal_id)
    return {"ok": True}
```

- [ ] **Step 5: Register the router**

In `backend/main.py`, change the import to include `goals`:
```python
from backend.api import budgets, goals, overview, people, recurring, transactions
```
and add after the `recurring` include:
```python
    app.include_router(goals.router, prefix="/api")
```

- [ ] **Step 6: Run it (passes)**

Run: `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api/test_goals.py -q`
Expected: 5 passed.

- [ ] **Step 7: Full API suite (no regressions)**

Run: `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api -q`
Expected: all pass (25 total: 20 prior + 5 new).

- [ ] **Step 8: Commit**

```bash
git add backend/api/goals.py backend/schemas.py backend/main.py tests/api/test_goals.py
git commit -m "feat(api): goals router (progress + add + update saved + delete)"
```

---

### Task 2: Goals API client (frontend)

**Files:**
- Modify: `web/src/lib/api.ts`, `web/src/lib/api.test.ts`

**Interfaces:**
- Consumes: `apiGet`, `apiSend` (Plan 3).
- Produces: `type Goal`; `getGoals`, `addGoal`, `updateGoalSaved`, `deleteGoal`.

- [ ] **Step 1: Write the failing tests**

In `web/src/lib/api.test.ts`, extend the import line to add the four functions:
```ts
import { getOverview, getTransactions, updateTransaction, getBudgets, setBudget, deleteBudget, getRecurring, getGoals, addGoal, updateGoalSaved, deleteGoal } from "./api";
```
Append:
```ts
test("getGoals builds /api/goals with person_id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetchMock);
  await getGoals({ personId: 1 });
  expect(fetchMock.mock.calls[0][0]).toBe("/api/goals?person_id=1");
});

test("addGoal POSTs name + target + horizon", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await addGoal({ personId: 1, name: "Car", targetAmount: 20000 });
  const [url, opts] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/goals");
  expect(opts.method).toBe("POST");
  expect(JSON.parse(opts.body as string)).toMatchObject({ person_id: 1, name: "Car", target_amount: 20000, horizon: "short" });
});

test("updateGoalSaved PATCHes saved_amount", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await updateGoalSaved(7, 1500);
  const [url, opts] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/goals/7");
  expect(opts.method).toBe("PATCH");
  expect(JSON.parse(opts.body as string)).toEqual({ saved_amount: 1500 });
});

test("deleteGoal DELETEs by id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await deleteGoal(7);
  const [url, opts] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/goals/7");
  expect(opts.method).toBe("DELETE");
});
```

- [ ] **Step 2: Run it (fails)**

Run (PowerShell, Node on PATH): `npm --prefix web test -- src/lib/api.test.ts`
Expected: FAIL (functions not exported).

- [ ] **Step 3: Implement in `lib/api.ts`**

Append at the end of the file:
```ts
export type Goal = {
  id: number;
  person_id: number | null;
  name: string;
  target_amount: number;
  saved_amount: number;
  target_date: string | null;
  horizon: string;
  notes: string;
  percent: number;
  monthly_needed: number | null;
};

export const getGoals = (p: { personId?: number }) =>
  apiGet<Goal[]>("/goals", { person_id: p.personId });

export const addGoal = (g: { personId?: number; name: string; targetAmount: number; targetDate?: string; horizon?: string }) =>
  apiSend<{ ok: boolean }>("POST", "/goals", {
    person_id: g.personId, name: g.name, target_amount: g.targetAmount,
    target_date: g.targetDate, horizon: g.horizon ?? "short",
  });

export const updateGoalSaved = (id: number, savedAmount: number) =>
  apiSend<{ ok: boolean }>("PATCH", `/goals/${id}`, { saved_amount: savedAmount });

export const deleteGoal = (id: number) =>
  apiSend<{ ok: boolean }>("DELETE", `/goals/${id}`);
```

- [ ] **Step 4: Run it (passes)**

Run (PowerShell): `npm --prefix web test -- src/lib/api.test.ts`
Expected: 13 passed.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/api.ts web/src/lib/api.test.ts
git commit -m "feat(web): goals API client"
```

---

### Task 3: Goals page

**Files:**
- Create: `web/src/pages/Goals.tsx`, `web/src/pages/Goals.test.tsx`

**Interfaces:**
- Consumes: `getGoals`, `addGoal`, `updateGoalSaved`, `deleteGoal`, `Goal` (Task 2); `usePersona()`, `Money`, `formatMoney`.
- Produces: `export default function Goals()` — the route element for Task 4.

- [ ] **Step 1: Write the failing test**

Create `web/src/pages/Goals.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

const addGoal = vi.fn().mockResolvedValue({ ok: true });
const updateGoalSaved = vi.fn().mockResolvedValue({ ok: true });
const deleteGoal = vi.fn().mockResolvedValue({ ok: true });
const getGoals = vi.fn().mockResolvedValue([
  { id: 1, person_id: 1, name: "Emergency fund", target_amount: 10000, saved_amount: 2500, target_date: "2026-12-31", horizon: "short", notes: "", percent: 25, monthly_needed: 1250 },
  { id: 2, person_id: 1, name: "Vacation", target_amount: 5000, saved_amount: 5000, target_date: null, horizon: "short", notes: "", percent: 100, monthly_needed: null },
]);

vi.mock("@/lib/persona", () => ({
  usePersona: () => ({
    persona: "you", personId: 1, label: "Ada",
    people: [{ id: 1, name: "Ada" }, { id: 2, name: "Mara" }], setPersona: () => {},
  }),
}));
vi.mock("@/lib/api", () => ({
  getGoals: (...a: unknown[]) => getGoals(...a),
  addGoal: (...a: unknown[]) => addGoal(...a),
  updateGoalSaved: (...a: unknown[]) => updateGoalSaved(...a),
  deleteGoal: (...a: unknown[]) => deleteGoal(...a),
}));

import Goals from "./Goals";

afterEach(() => { addGoal.mockClear(); updateGoalSaved.mockClear(); deleteGoal.mockClear(); });

test("renders goals with progress", async () => {
  render(<Goals />);
  await waitFor(() => expect(screen.getByText("Emergency fund")).toBeInTheDocument());
  expect(screen.getByText("Vacation")).toBeInTheDocument();
});

test("editing saved calls updateGoalSaved", async () => {
  render(<Goals />);
  await waitFor(() => expect(screen.getByText("Emergency fund")).toBeInTheDocument());
  const saved = screen.getByDisplayValue("2500");
  await userEvent.clear(saved);
  await userEvent.type(saved, "3000");
  await userEvent.tab();
  expect(updateGoalSaved).toHaveBeenCalledWith(1, 3000);
});

test("removing a goal calls deleteGoal", async () => {
  render(<Goals />);
  await waitFor(() => expect(screen.getByText("Emergency fund")).toBeInTheDocument());
  const remove = screen.getAllByRole("button", { name: /remove/i });
  await userEvent.click(remove[0]);
  expect(deleteGoal).toHaveBeenCalledWith(1);
});
```

- [ ] **Step 2: Run it (fails — no module)**

Run (PowerShell): `npm --prefix web test -- src/pages/Goals.test.tsx`
Expected: FAIL (cannot find `./Goals`).

- [ ] **Step 3: Implement `pages/Goals.tsx`**

```tsx
import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { getGoals, addGoal, updateGoalSaved, deleteGoal, type Goal } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { Money, formatMoney } from "@/components/money";

const pill: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "6px 12px",
  fontSize: 13, background: "transparent", color: "var(--fl-ink)",
};

function GoalCard({ g, onSave, onRemove }: {
  g: Goal; onSave: (g: Goal, v: string) => void; onRemove: (g: Goal) => void;
}) {
  const pct = Math.min(Math.max(g.percent, 0), 100);
  const done = g.percent >= 100;
  return (
    <section className="frosted-card" style={{ padding: 20, display: "grid", gap: 10 }}>
      <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <span style={{ fontWeight: 700 }}>{g.name}</span>
        {g.target_date && <span style={{ color: "var(--fl-muted)", fontSize: 12 }}>by {g.target_date}</span>}
        <span style={{ marginLeft: "auto", fontVariantNumeric: "tabular-nums" }}>
          <input
            type="number"
            defaultValue={g.saved_amount}
            aria-label={`Saved toward ${g.name}`}
            onBlur={(e) => onSave(g, e.target.value)}
            style={{ ...pill, width: 110, padding: "4px 10px", textAlign: "right" }}
          />{" "}
          <span style={{ color: "var(--fl-muted)" }}>/ <Money value={g.target_amount} /></span>
        </span>
        <button
          onClick={() => onRemove(g)}
          aria-label={`Remove ${g.name} goal`}
          style={{ border: "none", background: "none", color: "var(--fl-muted)", cursor: "pointer", fontSize: 16, lineHeight: 1 }}
        >
          ✕
        </button>
      </div>
      <div style={{ height: 10, borderRadius: 999, background: "var(--fl-line)" }}>
        <div style={{ height: 10, width: `${pct}%`, borderRadius: 999, background: done ? "var(--pos)" : "var(--persona)", transition: "width .4s ease" }} />
      </div>
      <div style={{ display: "flex", gap: 8, fontSize: 12, color: "var(--fl-muted)" }}>
        <span style={{ fontWeight: 600, color: done ? "var(--pos)" : "var(--persona)" }}>
          {done ? "reached 🎉" : `${Math.round(g.percent)}%`}
        </span>
        {!done && g.monthly_needed != null && (
          <span>· {formatMoney(g.monthly_needed)}/mo to stay on track</span>
        )}
      </div>
    </section>
  );
}

export default function Goals() {
  const { personId, label } = usePersona();
  const [goals, setGoals] = useState<Goal[]>([]);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [target, setTarget] = useState("");
  const [targetDate, setTargetDate] = useState("");
  const [horizon, setHorizon] = useState("short");

  const load = useCallback(
    () => getGoals({ personId }).then(setGoals).catch(() => setGoals([])),
    [personId],
  );
  useEffect(() => { load(); }, [load]);

  const commitSaved = (g: Goal, value: string) => {
    const amount = Number(value);
    if (Number.isFinite(amount) && amount >= 0 && amount !== g.saved_amount) {
      updateGoalSaved(g.id, amount).then(load);
    }
  };
  const remove = (g: Goal) => deleteGoal(g.id).then(load);
  const submit = () => {
    const targetAmount = Number(target);
    const nm = name.trim();
    if (nm && Number.isFinite(targetAmount) && targetAmount > 0) {
      addGoal({ personId, name: nm, targetAmount, targetDate: targetDate || undefined, horizon }).then(() => {
        setName(""); setTarget(""); setTargetDate(""); setHorizon("short"); setAdding(false); load();
      });
    }
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>Goals · {label}</h1>
        <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>savings targets</span>
      </header>

      {goals.length === 0 && !adding && (
        <section className="frosted-card" style={{ padding: 32, textAlign: "center", color: "var(--fl-muted)" }}>
          No goals yet. Add a savings target to track your progress.
        </section>
      )}

      <div style={{ display: "grid", gap: 12 }}>
        {goals.map((g) => <GoalCard key={g.id} g={g} onSave={commitSaved} onRemove={remove} />)}
      </div>

      {adding ? (
        <section className="frosted-card" style={{ padding: 20, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input placeholder="Goal name" value={name} onChange={(e) => setName(e.target.value)} style={pill} />
          <input type="number" placeholder="Target amount" value={target} onChange={(e) => setTarget(e.target.value)} style={{ ...pill, width: 140 }} />
          <input type="date" aria-label="Target date" value={targetDate} onChange={(e) => setTargetDate(e.target.value)} style={pill} />
          <select aria-label="Horizon" value={horizon} onChange={(e) => setHorizon(e.target.value)} style={pill}>
            <option value="short">Short-term</option>
            <option value="long">Long-term</option>
          </select>
          <button onClick={submit} style={{ ...pill, fontWeight: 700, color: "var(--persona)" }}>Add goal</button>
          <button onClick={() => setAdding(false)} style={{ ...pill, color: "var(--fl-muted)" }}>Cancel</button>
        </section>
      ) : (
        <button onClick={() => setAdding(true)} style={{ ...pill, justifySelf: "start", color: "var(--persona)" }}>＋ Add a goal</button>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run it (passes)**

Run (PowerShell): `npm --prefix web test -- src/pages/Goals.test.tsx`
Expected: 3 passed.

- [ ] **Step 5: Full web suite + build**

Run (PowerShell):
```
npm --prefix web test
npm --prefix web run build
```
Expected: all suites pass (30 tests across 8 files); build OK.

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/Goals.tsx web/src/pages/Goals.test.tsx
git commit -m "feat(web): Goals page (progress bars + inline saved + add/delete)"
```

---

### Task 4: Wire the `/goals` route

**Files:**
- Modify: `web/src/routes.tsx`

- [ ] **Step 1: Import and swap the placeholder**

In `web/src/routes.tsx`, add near the other page imports:
```tsx
import Goals from "@/pages/Goals";
```
Replace:
```tsx
      { path: "goals", element: <PagePlaceholder title="Goals" /> },
```
with:
```tsx
      { path: "goals", element: <Goals /> },
```

- [ ] **Step 2: Build + full suite**

Run (PowerShell):
```
npm --prefix web run build
npm --prefix web test
```
Expected: build OK; all suites pass.

- [ ] **Step 3: Commit**

```bash
git add web/src/routes.tsx
git commit -m "feat(web): wire /goals route"
```

---

## Self-Review

**1. Spec coverage:** GET progress rows → Task 1 (`goal_progress`) ✓; persona You/Spouse→int, Joint→"all" → Task 1 `list_goals` ✓; add (shared when Joint) → Task 1 `create_goal` + `GoalCreate` ✓; update saved → Task 1 `update_goal` ✓; delete → Task 1 ✓; api client + Goal type → Task 2 ✓; progress cards + inline saved + pace hint + completed state → Task 3 `GoalCard` ✓; add form (name/target/date/horizon) → Task 3 ✓; empty state → Task 3 ✓; route wired → Task 4 ✓; refetch after mutation → Task 3 `load()` ✓.

**2. Placeholder scan:** every step has complete code/commands; no TBD/TODO. `PagePlaceholder` is the shipped component being replaced.

**3. Type/interface consistency:** `Goal` (Task 2) consumed unchanged in Task 3; backend row keys (goal fields + `percent`/`monthly_needed`) match the `Goal` type and `goal_progress` output; `addGoal`/`updateGoalSaved`/`deleteGoal` signatures match the call sites and the `GoalCreate`/`GoalSavedUpdate` bodies; `list_goals(person_id)` None→"all" matches the design; route element `<Goals/>` matches the default export. Test for "editing saved" relies on `defaultValue={g.saved_amount}` rendering `2500` (matches `getByDisplayValue("2500")`), and amount `3000 !== 2500` passes the change guard.

**Out of scope (later plans):** Net Worth (Plan 8), Settings, Import wizard, AI Insights, cutover.
