# UI Rewrite — Plan 4: Transactions Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `/transactions` placeholder with the full ledger — a TanStack data table of the active persona's transactions with inline category editing, a per-row include toggle, a filter bar, and column sort — wired to the live `/api/transactions` endpoints.

**Architecture:** A typed `lib/api.ts` gains `getTransactions` / `updateTransaction` over the existing `apiGet`/`apiSend`. `pages/Transactions.tsx` fetches the persona's rows, holds filter/sort state, and renders a `@tanstack/react-table` over a hand-written shadcn `table` primitive. Writes PATCH then patch the row in place from the response. The route table swaps the placeholder for the page.

**Tech Stack:** React 18, TypeScript, `@tanstack/react-table` v8, shadcn `table` (Tailwind v4), react-router v7, Vitest + Testing Library.

## Working Context
- Worktree `.claude/worktrees/ui-rewrite`, branch `feature/ui-rewrite`. Depends on **Plan 3 completed** (api client `apiGet`/`apiSend`, `usePersona()`, `<Money/>`, routing + `PagePlaceholder` all in place).
- Node commands: run npm/npx via **PowerShell**, not the Bash tool — the Bash tool cannot resolve `node` on PATH here (confirmed in Plan 2/3). Use `npm --prefix web ...`, non-interactive (a prompt hangs a subagent → report BLOCKED, don't wait).
- Design doc: `docs/superpowers/specs/2026-06-19-transactions-page-design.md`.
- Backend (already shipped, do NOT modify): `GET /api/transactions?person_id=` → rows `{ id, person_id, date, description, amount, category, source, included (0|1), balance, person }`; `PATCH /api/transactions/{id}` body `{ category?, included? }` → updated row.

## Global Constraints (carried from the spec)
- Local-only, no auth/cloud. Reuse the engine; do NOT modify `modules/*.py` or `backend/*.py`. (spec §1)
- Persona model `You | Spouse | Joint`; query param is **`person_id`** (Joint ⇒ omit it). `you → people[0].id`, `spouse → people[1].id`. (spec §4, §9)
- Frosted Ledger: persona accent via `--persona`; You `--persona-you` #3B82F6, Spouse `--persona-spouse` #EC4899; income `--pos` green, spend `--neg` red; tabular numerals; soft 18px cards. (spec §3)

## File Structure (this plan)
```
web/src/
  lib/api.ts            # MODIFY: + Transaction type, getTransactions, updateTransaction
  lib/api.test.ts       # MODIFY: + 3 tests
  components/ui/table.tsx   # CREATE: shadcn table primitive
  pages/Transactions.tsx    # CREATE: the ledger page
  pages/Transactions.test.tsx  # CREATE
  routes.tsx            # MODIFY: /transactions -> <Transactions/>
```

---

### Task 1: Transactions API client

**Files:**
- Modify: `web/src/lib/api.ts`, `web/src/lib/api.test.ts`

**Interfaces:**
- Consumes: `apiGet<T>(path, params?)`, `apiSend<T>(method, path, body?)` (from Plan 3).
- Produces:
  - `type Transaction = { id: number; person_id: number; date: string; description: string; amount: number; category: string; source: string; included: number; balance: number | null; person: string }`
  - `getTransactions(p: { personId?: number }): Promise<Transaction[]>`
  - `updateTransaction(id: number, body: { category?: string; included?: boolean }): Promise<Transaction>`

- [ ] **Step 1: Write the failing tests**

In `web/src/lib/api.test.ts`, change the import line to add the new functions:
```ts
import { getOverview, getTransactions, updateTransaction } from "./api";
```
Append these tests to the end of the file:
```ts
test("getTransactions builds /api/transactions with person_id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetchMock);
  await getTransactions({ personId: 1 });
  expect(fetchMock.mock.calls[0][0]).toBe("/api/transactions?person_id=1");
});

test("getTransactions omits person_id for Joint", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => [] });
  vi.stubGlobal("fetch", fetchMock);
  await getTransactions({});
  expect(fetchMock.mock.calls[0][0]).toBe("/api/transactions");
});

test("updateTransaction PATCHes category + included", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ id: 5 }) });
  vi.stubGlobal("fetch", fetchMock);
  await updateTransaction(5, { category: "Rent", included: false });
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/transactions/5");
  expect(init.method).toBe("PATCH");
  expect(JSON.parse(init.body as string)).toEqual({ category: "Rent", included: false });
});
```

- [ ] **Step 2: Run it (fails — no exports)**

Run (PowerShell): `npm --prefix web test -- src/lib/api.test.ts`
Expected: FAIL (`getTransactions`/`updateTransaction` are not exported).

- [ ] **Step 3: Implement in `lib/api.ts`**

Append after the existing `getOverview` export:
```ts
export type Transaction = {
  id: number;
  person_id: number;
  date: string;
  description: string;
  amount: number;
  category: string;
  source: string;
  included: number; // 0 | 1
  balance: number | null;
  person: string;
};

export const getTransactions = (p: { personId?: number }) =>
  apiGet<Transaction[]>("/transactions", { person_id: p.personId });

export const updateTransaction = (id: number, body: { category?: string; included?: boolean }) =>
  apiSend<Transaction>("PATCH", `/transactions/${id}`, body);
```

- [ ] **Step 4: Run it (passes)**

Run (PowerShell): `npm --prefix web test -- src/lib/api.test.ts`
Expected: 5 passed (2 existing overview + 3 new).

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/api.ts web/src/lib/api.test.ts
git commit -m "feat(web): transactions API client (list + update)"
```

---

### Task 2: Add `@tanstack/react-table` + shadcn `table` primitive

**Files:**
- Modify: `web/package.json` (dep)
- Create: `web/src/components/ui/table.tsx`

**Interfaces:**
- Produces: `Table, TableHeader, TableBody, TableRow, TableHead, TableCell` from `@/components/ui/table`; `@tanstack/react-table` importable.

- [ ] **Step 1: Install the dependency**

Run (PowerShell): `npm --prefix web install @tanstack/react-table`
Expected: adds `@tanstack/react-table` (v8) to `web/package.json` dependencies.

- [ ] **Step 2: Create the shadcn table primitive**

Create `web/src/components/ui/table.tsx` (canonical shadcn source; uses the project's `cn`):
```tsx
import * as React from "react";
import { cn } from "@/lib/utils";

function Table({ className, ...props }: React.ComponentProps<"table">) {
  return (
    <div className="relative w-full overflow-x-auto">
      <table data-slot="table" className={cn("w-full caption-bottom text-sm", className)} {...props} />
    </div>
  );
}

function TableHeader({ className, ...props }: React.ComponentProps<"thead">) {
  return <thead data-slot="table-header" className={cn("[&_tr]:border-b", className)} {...props} />;
}

function TableBody({ className, ...props }: React.ComponentProps<"tbody">) {
  return <tbody data-slot="table-body" className={cn("[&_tr:last-child]:border-0", className)} {...props} />;
}

function TableRow({ className, ...props }: React.ComponentProps<"tr">) {
  return <tr data-slot="table-row" className={cn("border-b transition-colors", className)} {...props} />;
}

function TableHead({ className, ...props }: React.ComponentProps<"th">) {
  return <th data-slot="table-head" className={cn("h-10 px-3 text-left align-middle font-medium whitespace-nowrap", className)} {...props} />;
}

function TableCell({ className, ...props }: React.ComponentProps<"td">) {
  return <td data-slot="table-cell" className={cn("px-3 py-2.5 align-middle whitespace-nowrap", className)} {...props} />;
}

export { Table, TableHeader, TableBody, TableRow, TableHead, TableCell };
```

- [ ] **Step 3: Build sanity**

Run (PowerShell): `npm --prefix web run build`
Expected: build OK (`tsc -b` clean — the primitive is unused until Task 3).

- [ ] **Step 4: Commit**

```bash
git add web/package.json web/package-lock.json web/src/components/ui/table.tsx
git commit -m "chore(web): add @tanstack/react-table + shadcn table primitive"
```

---

### Task 3: Transactions page (TanStack table)

**Files:**
- Create: `web/src/pages/Transactions.tsx`, `web/src/pages/Transactions.test.tsx`

**Interfaces:**
- Consumes: `getTransactions`, `updateTransaction`, `Transaction` (Task 1); `Table*` (Task 2); `usePersona()`, `<Money/>`.
- Produces: `export default function Transactions()` — the route element used in Task 4.

- [ ] **Step 1: Write the failing test**

Create `web/src/pages/Transactions.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

const updateTransaction = vi.fn().mockResolvedValue({});

vi.mock("@/lib/persona", () => ({
  usePersona: () => ({
    persona: "you", personId: 1, label: "Ada",
    people: [{ id: 1, name: "Ada" }, { id: 2, name: "Mara" }], setPersona: () => {},
  }),
}));
vi.mock("@/lib/api", () => ({
  getTransactions: vi.fn().mockResolvedValue([
    { id: 1, person_id: 1, date: "2026-05-02", description: "Trader Joes", amount: -84.2, category: "Groceries", source: "card", included: 1, balance: null, person: "Ada" },
    { id: 2, person_id: 1, date: "2026-05-03", description: "Paycheck", amount: 5000, category: "Income", source: "bank", included: 1, balance: null, person: "Ada" },
    { id: 3, person_id: 1, date: "2026-05-05", description: "Netflix", amount: -15.99, category: "Subscriptions", source: "card", included: 1, balance: null, person: "Ada" },
  ]),
  updateTransaction: (...args: unknown[]) => updateTransaction(...args),
}));

import Transactions from "./Transactions";

afterEach(() => updateTransaction.mockClear());

test("renders the persona's transactions", async () => {
  render(<Transactions />);
  await waitFor(() => expect(screen.getByText("Trader Joes")).toBeInTheDocument());
  expect(screen.getByText("Paycheck")).toBeInTheDocument();
  expect(screen.getByText("Netflix")).toBeInTheDocument();
});

test("search filters rows by description", async () => {
  render(<Transactions />);
  await waitFor(() => expect(screen.getByText("Trader Joes")).toBeInTheDocument());
  await userEvent.type(screen.getByPlaceholderText(/search/i), "netflix");
  expect(screen.queryByText("Trader Joes")).not.toBeInTheDocument();
  expect(screen.getByText("Netflix")).toBeInTheDocument();
});

test("editing a category calls updateTransaction", async () => {
  render(<Transactions />);
  await waitFor(() => expect(screen.getByText("Netflix")).toBeInTheDocument());
  const input = screen.getByDisplayValue("Subscriptions");
  await userEvent.clear(input);
  await userEvent.type(input, "Streaming");
  await userEvent.tab();
  expect(updateTransaction).toHaveBeenCalledWith(3, { category: "Streaming" });
});

test("toggling Included calls updateTransaction", async () => {
  render(<Transactions />);
  await waitFor(() => expect(screen.getByText("Trader Joes")).toBeInTheDocument());
  const toggles = screen.getAllByRole("checkbox");
  await userEvent.click(toggles[0]);
  expect(updateTransaction).toHaveBeenCalledWith(1, { included: false });
});
```

- [ ] **Step 2: Run it (fails — no module)**

Run (PowerShell): `npm --prefix web test -- src/pages/Transactions.test.tsx`
Expected: FAIL (cannot find `./Transactions`).

- [ ] **Step 3: Implement `pages/Transactions.tsx`**

```tsx
import { useEffect, useMemo, useState, type CSSProperties } from "react";
import {
  flexRender,
  getCoreRowModel,
  getFilteredRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import { getTransactions, updateTransaction, type Transaction } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { Money } from "@/components/money";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";

type IncludeFilter = "all" | "in" | "out";
type Person = { id: number; name: string };

// ponytail: persona colors are keyed by people[0]/[1] (You/Spouse). Ceiling: only the
// first two people get a signature color; a third+ person falls back to the hairline.
const personaColor = (personId: number, people: Person[]) =>
  personId === people[0]?.id ? "var(--persona-you)"
  : personId === people[1]?.id ? "var(--persona-spouse)"
  : "var(--fl-line)";

const pill: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "6px 12px",
  fontSize: 13, background: "transparent", color: "var(--fl-ink)",
};

export default function Transactions() {
  const { personId, persona, people } = usePersona();
  const [data, setData] = useState<Transaction[]>([]);
  const [sorting, setSorting] = useState<SortingState>([]);
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("all");
  const [include, setInclude] = useState<IncludeFilter>("all");

  useEffect(() => {
    let alive = true;
    getTransactions({ personId }).then((d) => alive && setData(d)).catch(() => alive && setData([]));
    return () => { alive = false; };
  }, [personId]);

  const isJoint = persona === "joint";

  const categories = useMemo(
    () => Array.from(new Set(data.map((t) => t.category))).sort(),
    [data],
  );

  // Write through: PATCH, then replace the row in place from the response.
  const patch = (id: number, body: { category?: string; included?: boolean }) =>
    updateTransaction(id, body)
      .then((row) => setData((d) => d.map((t) => (t.id === id ? { ...t, ...row } : t))))
      .catch(() => {});

  const rows = useMemo(
    () =>
      data.filter(
        (t) =>
          (category === "all" || t.category === category) &&
          (include === "all" || (include === "in" ? t.included === 1 : t.included === 0)),
      ),
    [data, category, include],
  );

  const columns = useMemo<ColumnDef<Transaction>[]>(() => {
    const cols: ColumnDef<Transaction>[] = [
      {
        accessorKey: "date",
        header: "Date",
        cell: (c) => <span style={{ color: "var(--fl-muted)", fontVariantNumeric: "tabular-nums" }}>{c.getValue<string>()}</span>,
      },
      { accessorKey: "description", header: "Description" },
    ];
    if (isJoint) {
      cols.push({
        accessorKey: "person",
        header: "Person",
        enableSorting: false,
        cell: (c) => (
          <span style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
            <span style={{ width: 8, height: 8, borderRadius: 999, background: personaColor(c.row.original.person_id, people) }} />
            {c.getValue<string>()}
          </span>
        ),
      });
    }
    cols.push(
      {
        accessorKey: "category",
        header: "Category",
        enableSorting: false,
        cell: (c) => {
          const row = c.row.original;
          return (
            <input
              list="hf-categories"
              defaultValue={row.category}
              aria-label={`Category for ${row.description}`}
              onBlur={(e) => {
                const v = e.target.value.trim();
                if (v && v !== row.category) patch(row.id, { category: v });
              }}
              style={{ ...pill, padding: "4px 10px", maxWidth: 160 }}
            />
          );
        },
      },
      {
        accessorKey: "amount",
        header: "Amount",
        cell: (c) => <div style={{ textAlign: "right" }}><Money value={c.getValue<number>()} colored /></div>,
      },
      {
        accessorKey: "included",
        header: "In",
        enableSorting: false,
        cell: (c) => {
          const row = c.row.original;
          return (
            <input
              type="checkbox"
              checked={row.included === 1}
              aria-label={`Include ${row.description}`}
              onChange={(e) => patch(row.id, { included: e.target.checked })}
            />
          );
        },
      },
    );
    return cols;
  }, [isJoint, people]);

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting, globalFilter: search },
    onSortingChange: setSorting,
    onGlobalFilterChange: setSearch,
    globalFilterFn: (row, _id, value) => {
      const q = String(value).toLowerCase();
      return (
        row.original.description.toLowerCase().includes(q) ||
        row.original.category.toLowerCase().includes(q)
      );
    },
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
    getFilteredRowModel: getFilteredRowModel(),
  });

  const visible = table.getRowModel().rows;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>Transactions</h1>
        <div style={{ marginLeft: "auto", display: "flex", gap: 8, flexWrap: "wrap" }}>
          <input placeholder="Search…" value={search} onChange={(e) => setSearch(e.target.value)} style={pill} />
          <select value={category} onChange={(e) => setCategory(e.target.value)} style={pill}>
            <option value="all">All categories</option>
            {categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select>
          <select value={include} onChange={(e) => setInclude(e.target.value as IncludeFilter)} style={pill}>
            <option value="all">All</option>
            <option value="in">Included</option>
            <option value="out">Excluded</option>
          </select>
        </div>
      </header>

      <datalist id="hf-categories">
        {categories.map((c) => <option key={c} value={c} />)}
      </datalist>

      <section className="frosted-card" style={{ padding: 8 }}>
        <Table>
          <TableHeader>
            {table.getHeaderGroups().map((hg) => (
              <TableRow key={hg.id}>
                {hg.headers.map((h) => {
                  const sortable = h.column.getCanSort();
                  const dir = h.column.getIsSorted();
                  return (
                    <TableHead
                      key={h.id}
                      onClick={sortable ? h.column.getToggleSortingHandler() : undefined}
                      style={{
                        cursor: sortable ? "pointer" : "default",
                        textAlign: h.column.id === "amount" ? "right" : "left",
                        color: dir ? "var(--persona)" : "var(--fl-muted)",
                        userSelect: "none", textTransform: "uppercase", fontSize: 11, letterSpacing: "0.06em",
                      }}
                    >
                      {flexRender(h.column.columnDef.header, h.getContext())}
                      {dir === "asc" ? " ▲" : dir === "desc" ? " ▼" : ""}
                    </TableHead>
                  );
                })}
              </TableRow>
            ))}
          </TableHeader>
          <TableBody>
            {visible.map((r) => {
              const muted = r.original.included === 0;
              return (
                <TableRow
                  key={r.id}
                  style={{
                    opacity: muted ? 0.45 : 1,
                    boxShadow: isJoint ? `inset 3px 0 0 0 ${personaColor(r.original.person_id, people)}` : undefined,
                  }}
                >
                  {r.getVisibleCells().map((cell) => (
                    <TableCell key={cell.id}>{flexRender(cell.column.columnDef.cell, cell.getContext())}</TableCell>
                  ))}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
        {visible.length === 0 && (
          <p style={{ color: "var(--fl-muted)", padding: 24, textAlign: "center" }}>No transactions match these filters.</p>
        )}
      </section>
    </div>
  );
}
```

- [ ] **Step 4: Run it (passes)**

Run (PowerShell): `npm --prefix web test -- src/pages/Transactions.test.tsx`
Expected: 4 passed.

- [ ] **Step 5: Full web test suite + build**

Run (PowerShell):
```
npm --prefix web test
npm --prefix web run build
```
Expected: all suites pass; build OK.

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/Transactions.tsx web/src/pages/Transactions.test.tsx
git commit -m "feat(web): Transactions data table (TanStack) with inline edit + filters"
```

---

### Task 4: Wire the `/transactions` route

**Files:**
- Modify: `web/src/routes.tsx`

**Interfaces:**
- Consumes: `Transactions` default export (Task 3).

- [ ] **Step 1: Import and swap the placeholder**

In `web/src/routes.tsx`, add the import near the top (with the other page imports):
```tsx
import Transactions from "@/pages/Transactions";
```
Then replace the transactions route line:
```tsx
      { path: "transactions", element: <PagePlaceholder title="Transactions" /> },
```
with:
```tsx
      { path: "transactions", element: <Transactions /> },
```

- [ ] **Step 2: Build + full test suite**

Run (PowerShell):
```
npm --prefix web run build
npm --prefix web test
```
Expected: build OK; all suites pass.

- [ ] **Step 3: End-to-end smoke (optional, recommended)**

Run the API + dev server, click Transactions in the sidebar; confirm rows load, search/category/include filters work, a category edit and an include toggle persist after a refresh, and persona switch refetches:
```bash
VPY="C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe"
"$VPY" -m uvicorn backend.main:app --port 8000 --log-level warning   # then: npm --prefix web run dev
```

- [ ] **Step 4: Commit**

```bash
git add web/src/routes.tsx
git commit -m "feat(web): wire /transactions route to the ledger page"
```

---

## Self-Review

**1. Spec coverage** (design doc): full ledger table → Task 3 ✓; inline category edit (datalist) → Task 3 ✓; include toggle → Task 3 ✓; filter bar (search/category/include) → Task 3 ✓; column sort (date, amount) → Task 3 ✓; persona-scoped fetch + Joint person spine → Task 3 ✓; TanStack + shadcn table → Task 2 ✓; api client → Task 1 ✓; route wired → Task 4 ✓. Out-of-scope items (add/delete, bulk, source/month filters, virtualization) intentionally excluded.

**2. Placeholder scan:** every step has complete code or an exact command; no TBD/TODO. `PagePlaceholder` is the existing shipped component being replaced, not a plan gap.

**3. Type/interface consistency:** `Transaction` (Task 1) is consumed unchanged in Task 3; `getTransactions({ personId })` / `updateTransaction(id, body)` signatures match between definition (Task 1) and call sites (Task 3); `Table*` exports (Task 2) match imports (Task 3); the route element `<Transactions/>` (Task 4) matches the default export (Task 3). Backend `person_id`/`{category,included}` shapes match `backend/api/transactions.py`.

**Out of scope (later plans):** Budgets (Plan 5), Recurring/Net Worth (Plan 6), Goals, Settings, Import wizard, AI Insights, cutover — each its own plan.
