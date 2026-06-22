# UI Rewrite — Plan 9: Settings Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `/settings` placeholder with a page to manage per-person **category** keyword rules and **vendor** groups (CRUD), plus **rename people** — backed by two new thin FastAPI routers over the engine's category/vendor CRUD (people rename already exists).

**Architecture:** `backend/api/categories.py` + `backend/api/vendors.py` delegate to `db.get_categories`/`upsert_category`/`delete_category` and the vendor equivalents. `lib/api.ts` gains the types + functions + `renamePerson`. `pages/Settings.tsx` has a People rename section, a person selector, and a shared `RuleSection` for categories and vendors.

**Tech Stack:** FastAPI + pytest (TestClient, temp-DB fixtures); React 18 + TS, Vitest + Testing Library.

## Working Context
- Worktree `.claude/worktrees/ui-rewrite`, branch `feature/ui-rewrite`. Depends on Plans 1–8.
- **npm/npx via PowerShell**, prepend the portable Node to PATH first:
  `$env:Path = "C:\Users\lahat\node\node-v24.16.0-win-x64;" + $env:Path`. Then `npm --prefix web ...` from the worktree root.
- **pytest via** `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest ...` from the worktree root.
- Design doc: `docs/superpowers/specs/2026-06-19-settings-page-design.md`.
- Engine (do NOT modify): `db.get_categories(person_id)` → `[{id, person_id, name, keywords, parent}]`; `db.upsert_category(person_id, name, keywords, parent=None)`; `db.delete_category(category_id)`; `db.get_vendors(person_id)` → `[{id, person_id, name, keywords}]`; `db.upsert_vendor(person_id, name, keywords)`; `db.delete_vendor(vendor_id)`. **`categories.person_id`/`vendors.person_id` are NOT NULL** (per-person; no Joint). `db.rename_person` already wired at `PATCH /api/people/{id}`.

## Global Constraints (carried from the spec)
- Local-only; reuse the engine; do NOT modify `modules/*.py`. (spec §1)
- Categories/vendors are **per-person** — every category/vendor request carries a real `person_id` (required). People rename is global. (design §Key constraint)
- Frosted Ledger: `--persona` accent, soft 18px cards. (spec §3)

## File Structure (this plan)
```
backend/schemas.py                # MODIFY: + CategoryUpsert, VendorUpsert
backend/api/categories.py         # CREATE
backend/api/vendors.py            # CREATE
backend/main.py                   # MODIFY: register both routers
tests/api/test_settings.py        # CREATE (categories + vendors)
web/src/lib/api.ts                # MODIFY: + types + 7 functions
web/src/lib/api.test.ts           # MODIFY: + 7 tests
web/src/pages/Settings.tsx        # CREATE
web/src/pages/Settings.test.tsx   # CREATE
web/src/routes.tsx                # MODIFY: /settings -> <Settings/>
```

---

### Task 1: Categories + Vendors routers (backend)

**Files:**
- Modify: `backend/schemas.py`, `backend/main.py`
- Create: `backend/api/categories.py`, `backend/api/vendors.py`, `tests/api/test_settings.py`

**Interfaces:**
- Consumes: `db.get_categories/upsert_category/delete_category`, `db.get_vendors/upsert_vendor/delete_vendor`.
- Produces: `GET/PUT /api/categories`, `DELETE /api/categories/{id}`; same under `/vendors`.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_settings.py`:
```python
def test_categories_list_add_delete(client, people):
    you = people[0]["id"]
    r = client.put("/api/categories", json={"person_id": you, "name": "Groceries", "keywords": "whole foods,trader"})
    assert r.status_code == 200
    cats = client.get("/api/categories", params={"person_id": you}).json()
    g = next(c for c in cats if c["name"] == "Groceries")
    assert g["keywords"] == "whole foods,trader"

    client.delete(f"/api/categories/{g['id']}")
    assert all(c["name"] != "Groceries" for c in client.get("/api/categories", params={"person_id": you}).json())


def test_category_upsert_updates_existing(client, people):
    you = people[0]["id"]
    client.put("/api/categories", json={"person_id": you, "name": "Dining", "keywords": "chipotle"})
    client.put("/api/categories", json={"person_id": you, "name": "Dining", "keywords": "chipotle,sweetgreen"})
    dining = [c for c in client.get("/api/categories", params={"person_id": you}).json() if c["name"] == "Dining"]
    assert len(dining) == 1
    assert dining[0]["keywords"] == "chipotle,sweetgreen"


def test_categories_scoped_to_person(client, people):
    you, spouse = people[0]["id"], people[1]["id"]
    client.put("/api/categories", json={"person_id": you, "name": "Mine", "keywords": ""})
    assert client.get("/api/categories", params={"person_id": spouse}).json() == []


def test_vendors_list_add_delete(client, people):
    you = people[0]["id"]
    r = client.put("/api/vendors", json={"person_id": you, "name": "Amazon", "keywords": "amazon,amzn"})
    assert r.status_code == 200
    vendors = client.get("/api/vendors", params={"person_id": you}).json()
    a = next(v for v in vendors if v["name"] == "Amazon")
    assert a["keywords"] == "amazon,amzn"

    client.delete(f"/api/vendors/{a['id']}")
    assert all(v["name"] != "Amazon" for v in client.get("/api/vendors", params={"person_id": you}).json())
```

- [ ] **Step 2: Run it (fails — no routes)**

Run: `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api/test_settings.py -q`
Expected: FAIL (404/405).

- [ ] **Step 3: Add the schemas**

In `backend/schemas.py`, append:
```python
class CategoryUpsert(BaseModel):
    person_id: int
    name: str
    keywords: str = ""
    parent: Optional[str] = None


class VendorUpsert(BaseModel):
    person_id: int
    name: str
    keywords: str = ""
```

- [ ] **Step 4: Create the routers**

Create `backend/api/categories.py`:
```python
from fastapi import APIRouter

from modules import database as db
from backend.schemas import CategoryUpsert

router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("")
def list_categories(person_id: int):
    return db.get_categories(person_id)


@router.put("")
def upsert_category(body: CategoryUpsert):
    db.upsert_category(body.person_id, body.name, body.keywords, body.parent)
    return {"ok": True}


@router.delete("/{category_id}")
def remove_category(category_id: int):
    db.delete_category(category_id)
    return {"ok": True}
```

Create `backend/api/vendors.py`:
```python
from fastapi import APIRouter

from modules import database as db
from backend.schemas import VendorUpsert

router = APIRouter(prefix="/vendors", tags=["vendors"])


@router.get("")
def list_vendors(person_id: int):
    return db.get_vendors(person_id)


@router.put("")
def upsert_vendor(body: VendorUpsert):
    db.upsert_vendor(body.person_id, body.name, body.keywords)
    return {"ok": True}


@router.delete("/{vendor_id}")
def remove_vendor(vendor_id: int):
    db.delete_vendor(vendor_id)
    return {"ok": True}
```

- [ ] **Step 5: Register the routers**

In `backend/main.py`, change the import to include both:
```python
from backend.api import budgets, categories, goals, networth, overview, people, recurring, transactions, vendors
```
and add after the `networth` include:
```python
    app.include_router(categories.router, prefix="/api")
    app.include_router(vendors.router, prefix="/api")
```

- [ ] **Step 6: Run it (passes)**

Run: `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api/test_settings.py -q`
Expected: 4 passed.

- [ ] **Step 7: Full API suite (no regressions)**

Run: `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api -q`
Expected: all pass (34 total: 30 prior + 4 new).

- [ ] **Step 8: Commit**

```bash
git add backend/api/categories.py backend/api/vendors.py backend/schemas.py backend/main.py tests/api/test_settings.py
git commit -m "feat(api): categories + vendors routers for Settings"
```

---

### Task 2: Settings API client (frontend)

**Files:**
- Modify: `web/src/lib/api.ts`, `web/src/lib/api.test.ts`

**Interfaces:**
- Consumes: `apiGet`, `apiSend` (Plan 3).
- Produces: `type Category`, `type Vendor`; `getCategories`, `upsertCategory`, `deleteCategory`, `getVendors`, `upsertVendor`, `deleteVendor`, `renamePerson`.

- [ ] **Step 1: Write the failing tests**

In `web/src/lib/api.test.ts`, extend the import line to add the seven functions:
```ts
import { getOverview, getTransactions, updateTransaction, getBudgets, setBudget, deleteBudget, getRecurring, getGoals, addGoal, updateGoalSaved, deleteGoal, getNetWorth, addAccount, updateAccountBalance, deleteAccount, getCategories, upsertCategory, deleteCategory, getVendors, upsertVendor, deleteVendor, renamePerson } from "./api";
```
Append:
```ts
test("getCategories builds /api/categories with person_id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetchMock);
  await getCategories(1);
  expect(fetchMock.mock.calls[0][0]).toBe("/api/categories?person_id=1");
});

test("upsertCategory PUTs person_id + name + keywords", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await upsertCategory({ personId: 1, name: "Travel", keywords: "airbnb,delta" });
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/categories");
  expect(init.method).toBe("PUT");
  expect(JSON.parse(init.body as string)).toEqual({ person_id: 1, name: "Travel", keywords: "airbnb,delta" });
});

test("deleteCategory DELETEs by id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await deleteCategory(10);
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/categories/10");
  expect(init.method).toBe("DELETE");
});

test("getVendors builds /api/vendors with person_id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetchMock);
  await getVendors(2);
  expect(fetchMock.mock.calls[0][0]).toBe("/api/vendors?person_id=2");
});

test("upsertVendor PUTs person_id + name + keywords", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await upsertVendor({ personId: 2, name: "Amazon", keywords: "amazon,amzn" });
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/vendors");
  expect(init.method).toBe("PUT");
  expect(JSON.parse(init.body as string)).toEqual({ person_id: 2, name: "Amazon", keywords: "amazon,amzn" });
});

test("deleteVendor DELETEs by id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await deleteVendor(20);
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/vendors/20");
  expect(init.method).toBe("DELETE");
});

test("renamePerson PATCHes the people endpoint", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 1, name: "Adelaide" }) });
  vi.stubGlobal("fetch", fetchMock);
  await renamePerson(1, "Adelaide");
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/people/1");
  expect(init.method).toBe("PATCH");
  expect(JSON.parse(init.body as string)).toEqual({ name: "Adelaide" });
});
```

- [ ] **Step 2: Run it (fails)**

Run (PowerShell): `npm --prefix web test -- src/lib/api.test.ts`
Expected: FAIL (functions not exported).

- [ ] **Step 3: Implement in `lib/api.ts`**

Append at the end of the file:
```ts
export type Category = { id: number; person_id: number; name: string; keywords: string; parent?: string | null };
export type Vendor = { id: number; person_id: number; name: string; keywords: string };

export const getCategories = (personId: number) =>
  apiGet<Category[]>("/categories", { person_id: personId });
export const upsertCategory = (c: { personId: number; name: string; keywords: string }) =>
  apiSend<{ ok: boolean }>("PUT", "/categories", { person_id: c.personId, name: c.name, keywords: c.keywords });
export const deleteCategory = (id: number) =>
  apiSend<{ ok: boolean }>("DELETE", `/categories/${id}`);

export const getVendors = (personId: number) =>
  apiGet<Vendor[]>("/vendors", { person_id: personId });
export const upsertVendor = (v: { personId: number; name: string; keywords: string }) =>
  apiSend<{ ok: boolean }>("PUT", "/vendors", { person_id: v.personId, name: v.name, keywords: v.keywords });
export const deleteVendor = (id: number) =>
  apiSend<{ ok: boolean }>("DELETE", `/vendors/${id}`);

export const renamePerson = (id: number, name: string) =>
  apiSend<{ id: number; name: string }>("PATCH", `/people/${id}`, { name });
```

- [ ] **Step 4: Run it (passes)**

Run (PowerShell): `npm --prefix web test -- src/lib/api.test.ts`
Expected: 24 passed.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/api.ts web/src/lib/api.test.ts
git commit -m "feat(web): settings API client (categories + vendors + rename)"
```

---

### Task 3: Settings page

**Files:**
- Create: `web/src/pages/Settings.tsx`, `web/src/pages/Settings.test.tsx`

**Interfaces:**
- Consumes: `getPeople`, `renamePerson`, `getCategories`, `upsertCategory`, `deleteCategory`, `getVendors`, `upsertVendor`, `deleteVendor`, `Category`, `Vendor`, `Person` (Task 2 / Plan 3); `usePersona()`.
- Produces: `export default function Settings()` — the route element for Task 4.

- [ ] **Step 1: Write the failing test**

Create `web/src/pages/Settings.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

const renamePerson = vi.fn().mockResolvedValue({ id: 1, name: "Adelaide" });
const getPeople = vi.fn().mockResolvedValue([{ id: 1, name: "Ada" }, { id: 2, name: "Mara" }]);
const upsertCategory = vi.fn().mockResolvedValue({ ok: true });
const deleteCategory = vi.fn().mockResolvedValue({ ok: true });
const upsertVendor = vi.fn().mockResolvedValue({ ok: true });
const deleteVendor = vi.fn().mockResolvedValue({ ok: true });
const getCategories = vi.fn().mockResolvedValue([{ id: 10, person_id: 1, name: "Groceries", keywords: "whole foods" }]);
const getVendors = vi.fn().mockResolvedValue([{ id: 20, person_id: 1, name: "Amazon", keywords: "amazon,amzn" }]);

vi.mock("@/lib/persona", () => ({
  usePersona: () => ({
    persona: "you", personId: 1, label: "Ada",
    people: [{ id: 1, name: "Ada" }, { id: 2, name: "Mara" }], setPersona: () => {},
  }),
}));
vi.mock("@/lib/api", () => ({
  getPeople: (...a: unknown[]) => getPeople(...a),
  renamePerson: (...a: unknown[]) => renamePerson(...a),
  getCategories: (...a: unknown[]) => getCategories(...a),
  upsertCategory: (...a: unknown[]) => upsertCategory(...a),
  deleteCategory: (...a: unknown[]) => deleteCategory(...a),
  getVendors: (...a: unknown[]) => getVendors(...a),
  upsertVendor: (...a: unknown[]) => upsertVendor(...a),
  deleteVendor: (...a: unknown[]) => deleteVendor(...a),
}));

import Settings from "./Settings";

afterEach(() => {
  renamePerson.mockClear(); upsertCategory.mockClear(); deleteCategory.mockClear();
  upsertVendor.mockClear(); deleteVendor.mockClear();
});

test("renders categories and vendors for the active person", async () => {
  render(<Settings />);
  await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
  expect(screen.getByText("Amazon")).toBeInTheDocument();
});

test("renaming a person calls renamePerson", async () => {
  render(<Settings />);
  await waitFor(() => expect(screen.getByDisplayValue("Ada")).toBeInTheDocument());
  const input = screen.getByDisplayValue("Ada");
  await userEvent.clear(input);
  await userEvent.type(input, "Adelaide");
  await userEvent.tab();
  expect(renamePerson).toHaveBeenCalledWith(1, "Adelaide");
});

test("adding a category calls upsertCategory", async () => {
  render(<Settings />);
  await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
  await userEvent.type(screen.getByPlaceholderText("New category name"), "Travel");
  await userEvent.type(screen.getByPlaceholderText("Category keywords"), "airbnb,delta");
  await userEvent.click(screen.getByRole("button", { name: /add category/i }));
  expect(upsertCategory).toHaveBeenCalledWith({ personId: 1, name: "Travel", keywords: "airbnb,delta" });
});

test("deleting a category calls deleteCategory", async () => {
  render(<Settings />);
  await waitFor(() => expect(screen.getByText("Groceries")).toBeInTheDocument());
  await userEvent.click(screen.getByRole("button", { name: /remove category Groceries/i }));
  expect(deleteCategory).toHaveBeenCalledWith(10);
});
```

- [ ] **Step 2: Run it (fails — no module)**

Run (PowerShell): `npm --prefix web test -- src/pages/Settings.test.tsx`
Expected: FAIL (cannot find `./Settings`).

- [ ] **Step 3: Implement `pages/Settings.tsx`**

```tsx
import { useCallback, useEffect, useState, type CSSProperties } from "react";
import {
  getPeople, renamePerson,
  getCategories, upsertCategory, deleteCategory,
  getVendors, upsertVendor, deleteVendor,
  type Person, type Category, type Vendor,
} from "@/lib/api";
import { usePersona } from "@/lib/persona";

const pill: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "6px 12px",
  fontSize: 13, background: "transparent", color: "var(--fl-ink)",
};
const h2: CSSProperties = { fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--fl-muted)", margin: 0 };

type Rule = { id: number; name: string; keywords: string };

function RuleSection({ kind, items, onSave, onAdd, onRemove }: {
  kind: "category" | "vendor";
  items: Rule[];
  onSave: (r: Rule, keywords: string) => void;
  onAdd: (name: string, keywords: string) => void;
  onRemove: (r: Rule) => void;
}) {
  const [name, setName] = useState("");
  const [keywords, setKeywords] = useState("");
  const Title = kind === "category" ? "Categories" : "Vendor groups";
  const namePh = kind === "category" ? "New category name" : "New vendor name";
  const kwPh = kind === "category" ? "Category keywords" : "Vendor keywords";
  const addLabel = kind === "category" ? "Add category" : "Add vendor";

  const add = () => {
    if (name.trim()) { onAdd(name.trim(), keywords); setName(""); setKeywords(""); }
  };

  return (
    <section className="frosted-card" style={{ padding: 20, display: "grid", gap: 10 }}>
      <h2 style={h2}>{Title}</h2>
      {items.length === 0 && <div style={{ color: "var(--fl-muted)", fontSize: 13 }}>None yet.</div>}
      {items.map((r) => (
        <div key={r.id} style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontWeight: 700, minWidth: 120 }}>{r.name}</span>
          <input
            defaultValue={r.keywords}
            aria-label={`Keywords for ${kind} ${r.name}`}
            onBlur={(e) => onSave(r, e.target.value)}
            placeholder="comma-separated keywords"
            style={{ ...pill, flex: 1, minWidth: 160 }}
          />
          <button onClick={() => onRemove(r)} aria-label={`Remove ${kind} ${r.name}`}
            style={{ border: "none", background: "none", color: "var(--fl-muted)", cursor: "pointer", fontSize: 16, lineHeight: 1 }}>✕</button>
        </div>
      ))}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", borderTop: "1px solid var(--fl-line)", paddingTop: 10 }}>
        <input placeholder={namePh} value={name} onChange={(e) => setName(e.target.value)} style={{ ...pill, width: 160 }} />
        <input placeholder={kwPh} value={keywords} onChange={(e) => setKeywords(e.target.value)} style={{ ...pill, flex: 1, minWidth: 160 }} />
        <button onClick={add} style={{ ...pill, fontWeight: 700, color: "var(--persona)" }}>{addLabel}</button>
      </div>
    </section>
  );
}

export default function Settings() {
  const { personId: activePersonId } = usePersona();
  const [people, setPeople] = useState<Person[]>([]);
  const [selected, setSelected] = useState<number | null>(activePersonId ?? null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [vendors, setVendors] = useState<Vendor[]>([]);

  const loadPeople = useCallback(() => getPeople().then(setPeople).catch(() => setPeople([])), []);
  useEffect(() => { loadPeople(); }, [loadPeople]);

  // Default the selected person once people arrive (e.g. Joint -> first person).
  useEffect(() => {
    if (selected == null && people.length > 0) setSelected(people[0].id);
  }, [people, selected]);

  const loadRules = useCallback(() => {
    if (selected == null) return;
    getCategories(selected).then(setCategories).catch(() => setCategories([]));
    getVendors(selected).then(setVendors).catch(() => setVendors([]));
  }, [selected]);
  useEffect(() => { loadRules(); }, [loadRules]);

  const rename = (p: Person, value: string) => {
    const name = value.trim();
    if (name && name !== p.name) renamePerson(p.id, name).then(loadPeople);
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>Settings</h1>
        <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>people, categories & vendor groups</span>
      </header>

      <section className="frosted-card" style={{ padding: 20, display: "grid", gap: 10 }}>
        <h2 style={h2}>People</h2>
        {people.map((p) => (
          <div key={p.id} style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <input
              defaultValue={p.name}
              aria-label={`Name for person ${p.id}`}
              onBlur={(e) => rename(p, e.target.value)}
              style={{ ...pill, width: 220 }}
            />
          </div>
        ))}
      </section>

      <section className="frosted-card" style={{ padding: 16, display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
        <span style={h2}>Editing rules for</span>
        {people.map((p) => (
          <button
            key={p.id}
            onClick={() => setSelected(p.id)}
            aria-pressed={selected === p.id}
            style={{ ...pill, fontWeight: selected === p.id ? 700 : 500, background: selected === p.id ? "var(--persona)" : "transparent", color: selected === p.id ? "#fff" : "var(--fl-ink)" }}
          >
            {p.name}
          </button>
        ))}
      </section>

      <RuleSection
        kind="category"
        items={categories}
        onSave={(r, keywords) => { if (selected != null && keywords !== r.keywords) upsertCategory({ personId: selected, name: r.name, keywords }).then(loadRules); }}
        onAdd={(name, keywords) => { if (selected != null) upsertCategory({ personId: selected, name, keywords }).then(loadRules); }}
        onRemove={(r) => deleteCategory(r.id).then(loadRules)}
      />

      <RuleSection
        kind="vendor"
        items={vendors}
        onSave={(r, keywords) => { if (selected != null && keywords !== r.keywords) upsertVendor({ personId: selected, name: r.name, keywords }).then(loadRules); }}
        onAdd={(name, keywords) => { if (selected != null) upsertVendor({ personId: selected, name, keywords }).then(loadRules); }}
        onRemove={(r) => deleteVendor(r.id).then(loadRules)}
      />
    </div>
  );
}
```

- [ ] **Step 4: Run it (passes)**

Run (PowerShell): `npm --prefix web test -- src/pages/Settings.test.tsx`
Expected: 4 passed.

- [ ] **Step 5: Full web suite + build**

Run (PowerShell):
```
npm --prefix web test
npm --prefix web run build
```
Expected: all suites pass (41 tests across 10 files); build OK.

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/Settings.tsx web/src/pages/Settings.test.tsx
git commit -m "feat(web): Settings page (rename people + categories + vendor groups)"
```

---

### Task 4: Wire the `/settings` route

**Files:**
- Modify: `web/src/routes.tsx`

- [ ] **Step 1: Import and swap the placeholder**

In `web/src/routes.tsx`, add near the other page imports:
```tsx
import Settings from "@/pages/Settings";
```
Replace:
```tsx
      { path: "settings", element: <PagePlaceholder title="Settings" /> },
```
with:
```tsx
      { path: "settings", element: <Settings /> },
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
git commit -m "feat(web): wire /settings route"
```

---

## Self-Review

**1. Spec coverage:** categories GET/PUT/DELETE → Task 1 ✓; vendors GET/PUT/DELETE → Task 1 ✓; per-person `person_id` required → Task 1 (`person_id: int`) ✓; api client + `renamePerson` reuse → Task 2 ✓; People rename section → Task 3 ✓; person selector defaulting to active persona / first person → Task 3 ✓; categories + vendors `RuleSection` (list, inline keyword edit, add, delete) → Task 3 ✓; route wired → Task 4 ✓; refetch after mutation → Task 3 `loadRules`/`loadPeople` ✓.

**2. Placeholder scan:** every step has complete code/commands; no TBD/TODO. `PagePlaceholder` is the shipped component being replaced.

**3. Type/interface consistency:** `Category`/`Vendor`/`Person` (Task 2 / Plan 3) consumed unchanged in Task 3; backend row keys match the types; `upsertCategory`/`upsertVendor` send `{person_id,name,keywords}` matching `CategoryUpsert`/`VendorUpsert`; `renamePerson(id,name)` → `PATCH /people/{id}` body `{name}` matches the existing `PersonUpdate`. Test relies on: `getByDisplayValue("Ada")` being the unique person-name input (category keyword input value is "whole foods"); add-category targets unique placeholders `New category name`/`Category keywords` and button `Add category`; delete targets `aria-label="Remove category Groceries"`. Selected person defaults to `activePersonId` (1) so `getCategories(1)` matches the mock.

**Out of scope (later plans):** Import wizard, AI Insights, cutover (retire `app.py`, README).
