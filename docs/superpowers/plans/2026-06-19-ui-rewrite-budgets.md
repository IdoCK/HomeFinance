# UI Rewrite — Plan 5: Budgets Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `/budgets` placeholder with a pace-aware budget-vs-actual page for the current month, backed by a new thin FastAPI budgets router over the engine's `analytics.budget_status`.

**Architecture:** `backend/api/budgets.py` exposes GET (status) / PUT (upsert) / DELETE, each delegating to `modules/`. `lib/api.ts` gains `getBudgets`/`setBudget`/`deleteBudget`. `pages/Budgets.tsx` renders one pace-meter row per budgeted category; mutations re-fetch so status recomputes server-side.

**Tech Stack:** FastAPI + pytest (TestClient, temp-DB fixtures); React 18 + TS, Vitest + Testing Library.

## Working Context
- Worktree `.claude/worktrees/ui-rewrite`, branch `feature/ui-rewrite`. Depends on Plans 1–4.
- **npm/npx via PowerShell** (`npm --prefix web ...`), non-interactive (Bash can't resolve `node`).
- **pytest via the venv python**: `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest ...` (works from the Bash tool with the explicit path, or PowerShell). Run from the worktree root.
- Design doc: `docs/superpowers/specs/2026-06-19-budgets-page-design.md`.
- Engine (do NOT modify): `analytics.budget_status(txns, budgets, parents=None, as_of=None)` → per-row `{**budget, spent, budget, expected_to_date, projected_eom, pct, status}`, `status ∈ {on_track, ahead, over}`, current calendar month, pro-rated to today, parents roll up children. `db.get_budgets(person_id=None)` (None ⇒ household, `person_id IS NULL`), `db.set_budget(person_id, category, amount)` (upsert), `db.delete_budget(id)`, `db.category_parents(person_id)`, `db.get_transactions(person_id)`, `db.add_transactions(person_id, rows)`.

## Global Constraints (carried from the spec)
- Local-only; reuse the engine; do NOT modify `modules/*.py`. (spec §1)
- **Persona model for budgets** (differs from Transactions): You → `people[0].id`, Spouse → `people[1].id`, **Joint → `person_id=None`** (household budget set vs everyone's merged spend; `parents = {}` in Joint). (design §Persona)
- Frosted Ledger: `--persona` accent; `--neg` red; amber `#F59E0B` for "ahead"; tabular numerals; soft 18px cards. (spec §3)

## File Structure (this plan)
```
backend/api/budgets.py        # CREATE: GET/PUT/DELETE budgets router
backend/schemas.py            # MODIFY: + BudgetUpsert
backend/main.py               # MODIFY: register budgets router
tests/api/test_budgets.py     # CREATE
web/src/lib/api.ts            # MODIFY: + Budget type, getBudgets/setBudget/deleteBudget
web/src/lib/api.test.ts       # MODIFY: + tests
web/src/pages/Budgets.tsx     # CREATE
web/src/pages/Budgets.test.tsx  # CREATE
web/src/routes.tsx            # MODIFY: /budgets -> <Budgets/>
```

---

### Task 1: Budgets API router (backend)

**Files:**
- Create: `backend/api/budgets.py`, `tests/api/test_budgets.py`
- Modify: `backend/schemas.py`, `backend/main.py`

**Interfaces:**
- Consumes: `analytics.budget_status`, `db.get_budgets/set_budget/delete_budget/category_parents/get_transactions` (engine).
- Produces:
  - `GET /api/budgets?person_id=` → `list` of `{ id, person_id, category, amount, budget, spent, expected_to_date, projected_eom, pct, status }`.
  - `PUT /api/budgets` body `{ person_id?: int|null, category: str, amount: float }` → `{ ok: true }`.
  - `DELETE /api/budgets/{id}` → `{ ok: true }`.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_budgets.py`:
```python
from datetime import date


def test_budgets_status_for_current_month(client, people):
    from modules import database as db
    you = people[0]["id"]
    today = date.today().isoformat()
    db.add_transactions(you, [
        {"date": today, "description": "Whole Foods", "amount": -120.0,
         "category": "Groceries", "source": "card"},
    ])
    db.set_budget(you, "Groceries", 400.0)

    r = client.get("/api/budgets", params={"person_id": you})
    assert r.status_code == 200
    g = next(b for b in r.json() if b["category"] == "Groceries")
    assert g["budget"] == 400.0
    assert g["spent"] == 120.0
    assert g["status"] in ("on_track", "ahead", "over")


def test_put_budget_upserts(client, people):
    you = people[0]["id"]
    r = client.put("/api/budgets", json={"person_id": you, "category": "Rent", "amount": 2000.0})
    assert r.status_code == 200
    rows = client.get("/api/budgets", params={"person_id": you}).json()
    assert any(b["category"] == "Rent" and b["budget"] == 2000.0 for b in rows)


def test_delete_budget(client, people):
    you = people[0]["id"]
    client.put("/api/budgets", json={"person_id": you, "category": "Rent", "amount": 2000.0})
    bid = next(b["id"] for b in client.get("/api/budgets", params={"person_id": you}).json()
               if b["category"] == "Rent")
    assert client.delete(f"/api/budgets/{bid}").status_code == 200
    rows = client.get("/api/budgets", params={"person_id": you}).json()
    assert not any(b["category"] == "Rent" for b in rows)
```

- [ ] **Step 2: Run it (fails — no route)**

Run: `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api/test_budgets.py -q`
Expected: FAIL (404 — `/api/budgets` not registered).

- [ ] **Step 3: Add the request schema**

In `backend/schemas.py`, append:
```python
class BudgetUpsert(BaseModel):
    person_id: Optional[int] = None
    category: str
    amount: float
```
(`Optional` is already imported at the top of the file.)

- [ ] **Step 4: Create the router**

Create `backend/api/budgets.py`:
```python
from typing import Optional

from fastapi import APIRouter

from modules import database as db
from modules import analytics
from backend.schemas import BudgetUpsert

router = APIRouter(prefix="/budgets", tags=["budgets"])


@router.get("")
def list_budgets(person_id: Optional[int] = None):
    """person_id omitted -> household budgets (person_id IS NULL) vs everyone's spend."""
    txns = db.get_transactions(person_id)
    budgets = db.get_budgets(person_id)
    parents = db.category_parents(person_id) if person_id is not None else {}
    return analytics.budget_status(txns, budgets, parents)


@router.put("")
def upsert_budget(body: BudgetUpsert):
    db.set_budget(body.person_id, body.category, body.amount)
    return {"ok": True}


@router.delete("/{budget_id}")
def remove_budget(budget_id: int):
    db.delete_budget(budget_id)
    return {"ok": True}
```

- [ ] **Step 5: Register the router**

In `backend/main.py`, change the import line:
```python
from backend.api import budgets, overview, people, transactions
```
and add, after the `transactions` include:
```python
    app.include_router(budgets.router, prefix="/api")
```

- [ ] **Step 6: Run it (passes)**

Run: `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api/test_budgets.py -q`
Expected: 3 passed.

- [ ] **Step 7: Full API suite (no regressions)**

Run: `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api -q`
Expected: all pass (existing + 3 new).

- [ ] **Step 8: Commit**

```bash
git add backend/api/budgets.py backend/schemas.py backend/main.py tests/api/test_budgets.py
git commit -m "feat(api): budgets router (status + upsert + delete)"
```

---

### Task 2: Budgets API client (frontend)

**Files:**
- Modify: `web/src/lib/api.ts`, `web/src/lib/api.test.ts`

**Interfaces:**
- Consumes: `apiGet`, `apiSend` (Plan 3).
- Produces:
  - `type Budget = { id: number; person_id: number | null; category: string; amount: number; budget: number; spent: number; expected_to_date: number; projected_eom: number; pct: number; status: "on_track" | "ahead" | "over" }`
  - `getBudgets(p: { personId?: number }): Promise<Budget[]>`
  - `setBudget(b: { personId?: number; category: string; amount: number }): Promise<{ ok: boolean }>`
  - `deleteBudget(id: number): Promise<{ ok: boolean }>`

- [ ] **Step 1: Write the failing tests**

In `web/src/lib/api.test.ts`, extend the import:
```ts
import { getOverview, getTransactions, updateTransaction, getBudgets, setBudget, deleteBudget } from "./api";
```
Append:
```ts
test("getBudgets builds /api/budgets with person_id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetchMock);
  await getBudgets({ personId: 1 });
  expect(fetchMock.mock.calls[0][0]).toBe("/api/budgets?person_id=1");
});

test("setBudget PUTs person_id + category + amount", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await setBudget({ personId: 1, category: "Rent", amount: 2000 });
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/budgets");
  expect(init.method).toBe("PUT");
  expect(JSON.parse(init.body as string)).toEqual({ person_id: 1, category: "Rent", amount: 2000 });
});

test("deleteBudget DELETEs by id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await deleteBudget(7);
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/budgets/7");
  expect(init.method).toBe("DELETE");
});
```

- [ ] **Step 2: Run it (fails)**

Run (PowerShell): `npm --prefix web test -- src/lib/api.test.ts`
Expected: FAIL (3 new fail; existing pass).

- [ ] **Step 3: Implement in `lib/api.ts`**

Append after the `updateTransaction` export:
```ts
export type Budget = {
  id: number;
  person_id: number | null;
  category: string;
  amount: number;
  budget: number;
  spent: number;
  expected_to_date: number;
  projected_eom: number;
  pct: number;
  status: "on_track" | "ahead" | "over";
};

export const getBudgets = (p: { personId?: number }) =>
  apiGet<Budget[]>("/budgets", { person_id: p.personId });

export const setBudget = (b: { personId?: number; category: string; amount: number }) =>
  apiSend<{ ok: boolean }>("PUT", "/budgets", { person_id: b.personId, category: b.category, amount: b.amount });

export const deleteBudget = (id: number) =>
  apiSend<{ ok: boolean }>("DELETE", `/budgets/${id}`);
```
Note: `JSON.stringify` drops `person_id: undefined` for Joint, so the backend defaults it to `None` (household).

- [ ] **Step 4: Run it (passes)**

Run (PowerShell): `npm --prefix web test -- src/lib/api.test.ts`
Expected: 8 passed (5 prior + 3 new).

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/api.ts web/src/lib/api.test.ts
git commit -m "feat(web): budgets API client"
```

---

### Task 3: Budgets page (pace meters)

**Files:**
- Create: `web/src/pages/Budgets.tsx`, `web/src/pages/Budgets.test.tsx`

**Interfaces:**
- Consumes: `getBudgets`, `setBudget`, `deleteBudget`, `Budget` (Task 2); `usePersona()`, `<Money/>`.
- Produces: `export default function Budgets()` — the route element for Task 4.

- [ ] **Step 1: Write the failing test**

Create `web/src/pages/Budgets.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

const setBudget = vi.fn().mockResolvedValue({ ok: true });
const deleteBudget = vi.fn().mockResolvedValue({ ok: true });
const getBudgets = vi.fn().mockResolvedValue([
  { id: 1, person_id: 1, category: "Groceries", amount: 400, budget: 400, spent: 312, expected_to_date: 252, projected_eom: 480, pct: 0.78, status: "ahead" },
  { id: 2, person_id: 1, category: "Rent", amount: 2000, budget: 2000, spent: 2000, expected_to_date: 1260, projected_eom: 2000, pct: 1.0, status: "over" },
]);

vi.mock("@/lib/persona", () => ({
  usePersona: () => ({
    persona: "you", personId: 1, label: "Ada",
    people: [{ id: 1, name: "Ada" }, { id: 2, name: "Mara" }], setPersona: () => {},
  }),
}));
vi.mock("@/lib/api", () => ({
  getBudgets: (...a: unknown[]) => getBudgets(...a),
  setBudget: (...a: unknown[]) => setBudget(...a),
  deleteBudget: (...a: unknown[]) => deleteBudget(...a),
}));

import Budgets from "./Budgets";

afterEach(() => { setBudget.mockClear(); deleteBudget.mockClear(); });

test("renders budgeted categories", async () => {
  render(<Budgets />);
  await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
  expect(screen.getByText("Rent")).toBeInTheDocument();
});

test("editing a cap calls setBudget", async () => {
  render(<Budgets />);
  await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
  const cap = screen.getByDisplayValue("400");
  await userEvent.clear(cap);
  await userEvent.type(cap, "500");
  await userEvent.tab();
  expect(setBudget).toHaveBeenCalledWith({ personId: 1, category: "Groceries", amount: 500 });
});

test("removing a budget calls deleteBudget", async () => {
  render(<Budgets />);
  await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
  const remove = screen.getAllByRole("button", { name: /remove/i });
  await userEvent.click(remove[0]);
  expect(deleteBudget).toHaveBeenCalledWith(1);
});
```

- [ ] **Step 2: Run it (fails — no module)**

Run (PowerShell): `npm --prefix web test -- src/pages/Budgets.test.tsx`
Expected: FAIL (cannot find `./Budgets`).

- [ ] **Step 3: Implement `pages/Budgets.tsx`**

```tsx
import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { getBudgets, setBudget, deleteBudget, type Budget } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { Money } from "@/components/money";

const STATUS_COLOR: Record<Budget["status"], string> = {
  on_track: "var(--persona)",
  ahead: "#F59E0B",
  over: "var(--neg)",
};
const STATUS_LABEL: Record<Budget["status"], string> = {
  on_track: "on pace",
  ahead: "running hot",
  over: "over budget",
};

const pill: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "6px 12px",
  fontSize: 13, background: "transparent", color: "var(--fl-ink)",
};

function PaceMeter({ b }: { b: Budget }) {
  const fillPct = Math.min(b.budget > 0 ? (b.spent / b.budget) * 100 : 0, 100);
  const tickPct = Math.min(b.budget > 0 ? (b.expected_to_date / b.budget) * 100 : 0, 100);
  return (
    <div style={{ position: "relative", height: 10, borderRadius: 999, background: "var(--fl-line)" }}>
      <div style={{ position: "absolute", top: 0, left: 0, height: "100%", width: `${fillPct}%`, background: STATUS_COLOR[b.status], borderRadius: 999, transition: "width .4s ease" }} />
      <div style={{ position: "absolute", top: -2, bottom: -2, left: `${tickPct}%`, width: 2, borderRadius: 2, background: "var(--fl-ink)", opacity: 0.5 }} aria-hidden />
    </div>
  );
}

export default function Budgets() {
  const { personId, label } = usePersona();
  const [budgets, setBudgets] = useState<Budget[]>([]);
  const [adding, setAdding] = useState(false);
  const [newCat, setNewCat] = useState("");
  const [newAmt, setNewAmt] = useState("");

  const load = useCallback(
    () => getBudgets({ personId }).then(setBudgets).catch(() => setBudgets([])),
    [personId],
  );
  useEffect(() => { load(); }, [load]);

  const commitCap = (b: Budget, value: string) => {
    const amount = Number(value);
    if (Number.isFinite(amount) && amount >= 0 && amount !== b.budget) {
      setBudget({ personId, category: b.category, amount }).then(load);
    }
  };

  const remove = (b: Budget) => deleteBudget(b.id).then(load);

  const addBudget = () => {
    const amount = Number(newAmt);
    const category = newCat.trim();
    if (category && Number.isFinite(amount) && amount >= 0) {
      setBudget({ personId, category, amount }).then(() => {
        setNewCat(""); setNewAmt(""); setAdding(false); load();
      });
    }
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>Budgets · {label}</h1>
        <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>this month, paced to today</span>
      </header>

      {budgets.length === 0 && !adding && (
        <section className="frosted-card" style={{ padding: 32, textAlign: "center", color: "var(--fl-muted)" }}>
          No budgets yet. Set a monthly cap for a category to track it.
        </section>
      )}

      <div style={{ display: "grid", gap: 12 }}>
        {budgets.map((b) => (
          <section key={b.id} className="frosted-card" style={{ padding: 20, display: "grid", gap: 10 }}>
            <div style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
              <span style={{ fontWeight: 700 }}>{b.category}</span>
              <span style={{ marginLeft: "auto", fontVariantNumeric: "tabular-nums" }}>
                <Money value={b.spent} /> <span style={{ color: "var(--fl-muted)" }}>/</span>{" "}
                <input
                  type="number"
                  defaultValue={b.budget}
                  aria-label={`Monthly cap for ${b.category}`}
                  onBlur={(e) => commitCap(b, e.target.value)}
                  style={{ ...pill, width: 96, padding: "4px 10px", textAlign: "right" }}
                />
              </span>
              <button
                onClick={() => remove(b)}
                aria-label={`Remove ${b.category} budget`}
                style={{ border: "none", background: "none", color: "var(--fl-muted)", cursor: "pointer", fontSize: 16, lineHeight: 1 }}
              >
                ✕
              </button>
            </div>
            <PaceMeter b={b} />
            <div style={{ display: "flex", gap: 8, fontSize: 12, color: STATUS_COLOR[b.status] }}>
              <span style={{ fontWeight: 600 }}>{STATUS_LABEL[b.status]}</span>
              <span style={{ color: "var(--fl-muted)" }}>
                · {Math.round(b.pct * 100)}% used · ~<Money value={b.projected_eom} /> projected
              </span>
            </div>
          </section>
        ))}
      </div>

      {adding ? (
        <section className="frosted-card" style={{ padding: 20, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input placeholder="Category" value={newCat} onChange={(e) => setNewCat(e.target.value)} style={pill} />
          <input type="number" placeholder="Monthly cap" value={newAmt} onChange={(e) => setNewAmt(e.target.value)} style={{ ...pill, width: 130 }} />
          <button onClick={addBudget} style={{ ...pill, fontWeight: 700, color: "var(--persona)" }}>Add budget</button>
          <button onClick={() => setAdding(false)} style={{ ...pill, color: "var(--fl-muted)" }}>Cancel</button>
        </section>
      ) : (
        <button onClick={() => setAdding(true)} style={{ ...pill, justifySelf: "start", color: "var(--persona)" }}>＋ Add a budget</button>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run it (passes)**

Run (PowerShell): `npm --prefix web test -- src/pages/Budgets.test.tsx`
Expected: 3 passed.

- [ ] **Step 5: Full web suite + build**

Run (PowerShell):
```
npm --prefix web test
npm --prefix web run build
```
Expected: all suites pass; build OK.

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/Budgets.tsx web/src/pages/Budgets.test.tsx
git commit -m "feat(web): Budgets page with pace meters + inline edit"
```

---

### Task 4: Wire the `/budgets` route

**Files:**
- Modify: `web/src/routes.tsx`

**Interfaces:**
- Consumes: `Budgets` default export (Task 3).

- [ ] **Step 1: Import and swap the placeholder**

In `web/src/routes.tsx`, add near the other page imports:
```tsx
import Budgets from "@/pages/Budgets";
```
Replace:
```tsx
      { path: "budgets", element: <PagePlaceholder title="Budgets" /> },
```
with:
```tsx
      { path: "budgets", element: <Budgets /> },
```

- [ ] **Step 2: Build + full suite**

Run (PowerShell):
```
npm --prefix web run build
npm --prefix web test
```
Expected: build OK; all suites pass.

- [ ] **Step 3: End-to-end smoke (optional)**

Run the API + dev server, click Budgets; confirm caps render with pace ticks, editing a cap persists, add/delete work, and persona switch (incl. Joint = household) refetches.

- [ ] **Step 4: Commit**

```bash
git add web/src/routes.tsx
git commit -m "feat(web): wire /budgets route"
```

---

## Self-Review

**1. Spec coverage:** GET status / PUT / DELETE router → Task 1 ✓; persona model incl. Joint=household (`parents={}`) → Task 1 `list_budgets` ✓; api client → Task 2 ✓; pace-meter rows w/ status color + tick → Task 3 `PaceMeter` ✓; inline cap edit → Task 3 `commitCap` ✓; add → Task 3 `addBudget` ✓; delete → Task 3 `remove` ✓; empty state + copy → Task 3 ✓; route wired → Task 4 ✓. Out-of-scope (historical budgets, parent-budget UI, category mgmt) excluded.

**2. Placeholder scan:** every step has complete code/commands; no TBD/TODO. `PagePlaceholder` is the shipped component being replaced.

**3. Type/interface consistency:** `Budget` (Task 2) consumed unchanged in Task 3; `getBudgets({personId})` / `setBudget({personId,category,amount})` / `deleteBudget(id)` signatures match call sites; backend GET row keys (`budget/spent/expected_to_date/projected_eom/pct/status`) match `analytics.budget_status` output and the `Budget` type; `BudgetUpsert` fields match the PUT body the client sends; route element `<Budgets/>` matches the default export.

**Out of scope (later plans):** Recurring/Net Worth (Plan 6), Goals, Settings, Import wizard, AI Insights, cutover.
