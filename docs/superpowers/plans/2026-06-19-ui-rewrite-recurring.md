# UI Rewrite — Plan 6: Recurring Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `/recurring` placeholder with a read-only page that surfaces detected subscriptions, the committed monthly spend, and anomaly flags — backed by a new thin FastAPI recurring router over the engine's detection functions.

**Architecture:** `backend/api/recurring.py` runs `analytics.recurring_charges` (fed per-person vendor rules) + `committed_monthly` + `recurring_anomalies` and returns one bundle. `lib/api.ts` gains `getRecurring`. `pages/Recurring.tsx` renders a committed-total hero, anomaly chips, and a charge list — no mutations.

**Tech Stack:** FastAPI + pytest (TestClient, temp-DB fixtures); React 18 + TS, Vitest + Testing Library.

## Working Context
- Worktree `.claude/worktrees/ui-rewrite`, branch `feature/ui-rewrite`. Depends on Plans 1–5.
- **npm/npx via PowerShell** (`npm --prefix web ...`); **pytest via** `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest ...` from the worktree root.
- Design doc: `docs/superpowers/specs/2026-06-19-recurring-page-design.md`.
- Engine (do NOT modify): `analytics.recurring_charges(txns, vendor_rules=None)` → list of `{vendor, category, cadence, kind, typical_amount, prior_typical, prior_stable, first_date, last_date, last_amount, next_expected, count, monthly_cost, annual_cost, confidence}`; `analytics.committed_monthly(recurring)` → `{fixed, variable, total}`; `analytics.recurring_anomalies(recurring, as_of=None)` → list of `{vendor, type, detail, ...}`. `vendor_of` expects `vendor_rules` as **`list of (name, [keywords])`**. `db.get_vendors(person_id)` → `[{id, person_id, name, keywords(comma-string)}]`; `db.upsert_vendor(person_id, name, keywords)`; `db.add_transactions(person_id, rows)`.

## Global Constraints (carried from the spec)
- Local-only; reuse the engine; do NOT modify `modules/*.py`. (spec §1)
- **Vendor rules:** for a real person, transform `db.get_vendors(pid)` dicts into `(name, [kw…])` tuples and pass to `recurring_charges`; Joint (`person_id=None`) passes `None`. (design §Backend)
- **Persona = natural model:** You→people[0], Spouse→people[1], Joint→merge everyone (no household special case). (design §Backend)
- Read-only page. Frosted Ledger: `--persona` accent; amber `#F59E0B`; tabular numerals; soft 18px cards. (spec §3)

## File Structure (this plan)
```
backend/api/recurring.py        # CREATE: GET recurring bundle
backend/main.py                 # MODIFY: register recurring router
tests/api/test_recurring.py     # CREATE
web/src/lib/api.ts              # MODIFY: + recurring types + getRecurring
web/src/lib/api.test.ts         # MODIFY: + test
web/src/pages/Recurring.tsx     # CREATE
web/src/pages/Recurring.test.tsx  # CREATE
web/src/routes.tsx              # MODIFY: /recurring -> <Recurring/>
```

---

### Task 1: Recurring API router (backend)

**Files:**
- Create: `backend/api/recurring.py`, `tests/api/test_recurring.py`
- Modify: `backend/main.py`

**Interfaces:**
- Consumes: `analytics.recurring_charges/committed_monthly/recurring_anomalies`, `db.get_transactions/get_vendors`.
- Produces: `GET /api/recurring?person_id=` → `{ charges: list, committed: {fixed,variable,total}, anomalies: list }`.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_recurring.py`:
```python
from datetime import date, timedelta


def _monthly(desc, n=4, amount=-15.99, category="Subscriptions"):
    today = date.today()
    return [
        {"date": (today - timedelta(days=30 * (n - 1 - i))).isoformat(),
         "description": desc, "amount": amount, "category": category, "source": "card"}
        for i in range(n)
    ]


def test_recurring_detects_monthly_subscription(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.add_transactions(you, _monthly("NETFLIX.COM"))

    r = client.get("/api/recurring", params={"person_id": you})
    assert r.status_code == 200
    data = r.json()
    nflx = next(c for c in data["charges"] if "netflix" in c["vendor"].lower())
    assert nflx["cadence"] == "monthly"
    assert nflx["kind"] == "fixed"
    assert data["committed"]["total"] > 0


def test_recurring_collapses_via_vendor_rule(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.upsert_vendor(you, "Amazon", "amazon,amzn")
    today = date.today()
    variants = ["AMAZON.COM", "AMZN MKTP US", "AMAZON.COM", "AMZN MKTP US"]
    rows = [
        {"date": (today - timedelta(days=30 * (3 - i))).isoformat(),
         "description": d, "amount": -12.99, "category": "Shopping", "source": "card"}
        for i, d in enumerate(variants)
    ]
    db.add_transactions(you, rows)

    data = client.get("/api/recurring", params={"person_id": you}).json()
    amazon = [c for c in data["charges"] if c["vendor"] == "Amazon"]
    assert len(amazon) == 1
    assert amazon[0]["count"] == 4
```

- [ ] **Step 2: Run it (fails — no route)**

Run: `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api/test_recurring.py -q`
Expected: FAIL (404 — `/api/recurring` not registered).

- [ ] **Step 3: Create the router**

Create `backend/api/recurring.py`:
```python
from typing import Optional

from fastapi import APIRouter

from modules import database as db
from modules import analytics

router = APIRouter(prefix="/recurring", tags=["recurring"])


def _vendor_rules(person_id: Optional[int]):
    """db.get_vendors dicts -> the (name, [keywords]) tuples vendor_of expects.
    None for Joint (vendor rules are per-person)."""
    if person_id is None:
        return None
    return [
        (v["name"], [k.strip() for k in (v["keywords"] or "").split(",") if k.strip()])
        for v in db.get_vendors(person_id)
    ]


@router.get("")
def list_recurring(person_id: Optional[int] = None):
    recurring = analytics.recurring_charges(
        db.get_transactions(person_id), _vendor_rules(person_id)
    )
    return {
        "charges": recurring,
        "committed": analytics.committed_monthly(recurring),
        "anomalies": analytics.recurring_anomalies(recurring),
    }
```

- [ ] **Step 4: Register the router**

In `backend/main.py`, change the import:
```python
from backend.api import budgets, overview, people, recurring, transactions
```
and add after the `budgets` include:
```python
    app.include_router(recurring.router, prefix="/api")
```

- [ ] **Step 5: Run it (passes)**

Run: `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api/test_recurring.py -q`
Expected: 2 passed.

- [ ] **Step 6: Full API suite (no regressions)**

Run: `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/api/recurring.py backend/main.py tests/api/test_recurring.py
git commit -m "feat(api): recurring router (charges + committed + anomalies)"
```

---

### Task 2: Recurring API client (frontend)

**Files:**
- Modify: `web/src/lib/api.ts`, `web/src/lib/api.test.ts`

**Interfaces:**
- Consumes: `apiGet` (Plan 3).
- Produces:
  - `type RecurringCharge`, `type RecurringAnomaly`, `type Committed`, `type RecurringData`
  - `getRecurring(p: { personId?: number }): Promise<RecurringData>`

- [ ] **Step 1: Write the failing test**

In `web/src/lib/api.test.ts`, extend the import line to add `getRecurring`:
```ts
import { getOverview, getTransactions, updateTransaction, getBudgets, setBudget, deleteBudget, getRecurring } from "./api";
```
Append:
```ts
test("getRecurring builds /api/recurring with person_id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ charges: [], committed: { fixed: 0, variable: 0, total: 0 }, anomalies: [] }) });
  vi.stubGlobal("fetch", fetchMock);
  await getRecurring({ personId: 2 });
  expect(fetchMock.mock.calls[0][0]).toBe("/api/recurring?person_id=2");
});
```

- [ ] **Step 2: Run it (fails)**

Run (PowerShell): `npm --prefix web test -- src/lib/api.test.ts`
Expected: FAIL (`getRecurring` not exported).

- [ ] **Step 3: Implement in `lib/api.ts`**

Append after the `deleteBudget` export:
```ts
export type RecurringCharge = {
  vendor: string;
  category: string | null;
  cadence: "weekly" | "monthly" | "quarterly" | "yearly";
  kind: "fixed" | "variable";
  typical_amount: number;
  prior_typical: number;
  prior_stable: boolean;
  first_date: string;
  last_date: string;
  last_amount: number;
  next_expected: string;
  count: number;
  monthly_cost: number;
  annual_cost: number;
  confidence: number;
};

export type RecurringAnomaly = {
  vendor: string;
  type: "price_change" | "possibly_canceled" | "new";
  detail: string;
  pct?: number;
  overdue_days?: number;
  age_days?: number;
};

export type Committed = { fixed: number; variable: number; total: number };

export type RecurringData = {
  charges: RecurringCharge[];
  committed: Committed;
  anomalies: RecurringAnomaly[];
};

export const getRecurring = (p: { personId?: number }) =>
  apiGet<RecurringData>("/recurring", { person_id: p.personId });
```

- [ ] **Step 4: Run it (passes)**

Run (PowerShell): `npm --prefix web test -- src/lib/api.test.ts`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/api.ts web/src/lib/api.test.ts
git commit -m "feat(web): recurring API client"
```

---

### Task 3: Recurring page

**Files:**
- Create: `web/src/pages/Recurring.tsx`, `web/src/pages/Recurring.test.tsx`

**Interfaces:**
- Consumes: `getRecurring`, `RecurringCharge`, `RecurringAnomaly`, `RecurringData` (Task 2); `usePersona()`, `formatMoney`.
- Produces: `export default function Recurring()` — the route element for Task 4.

- [ ] **Step 1: Write the failing test**

Create `web/src/pages/Recurring.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

const getRecurring = vi.fn().mockResolvedValue({
  charges: [
    { vendor: "Netflix", category: "Subscriptions", cadence: "monthly", kind: "fixed", typical_amount: 15.99, prior_typical: 15.99, prior_stable: true, first_date: "2026-01-05", last_date: "2026-06-05", last_amount: 15.99, next_expected: "2026-07-05", count: 6, monthly_cost: 15.99, annual_cost: 191.88, confidence: 0.95 },
    { vendor: "Comcast", category: "Utilities", cadence: "monthly", kind: "variable", typical_amount: 89, prior_typical: 85, prior_stable: true, first_date: "2026-01-10", last_date: "2026-06-10", last_amount: 102, next_expected: "2026-07-10", count: 6, monthly_cost: 89, annual_cost: 1068, confidence: 0.8 },
  ],
  committed: { fixed: 15.99, variable: 89, total: 104.99 },
  anomalies: [{ vendor: "Comcast", type: "price_change", detail: "85.00 -> 102.00", pct: 20 }],
});

vi.mock("@/lib/persona", () => ({
  usePersona: () => ({ persona: "joint", personId: undefined, label: "Joint", people: [], setPersona: () => {} }),
}));
vi.mock("@/lib/api", () => ({ getRecurring: (...a: unknown[]) => getRecurring(...a) }));

import Recurring from "./Recurring";

afterEach(() => getRecurring.mockClear());

test("renders detected subscriptions", async () => {
  render(<Recurring />);
  await waitFor(() => expect(screen.getByText("Netflix")).toBeInTheDocument());
  expect(screen.getByText("Comcast")).toBeInTheDocument();
});

test("shows the committed monthly total", async () => {
  render(<Recurring />);
  await waitFor(() => expect(screen.getByTestId("committed-total")).toHaveTextContent("$104.99"));
});

test("surfaces a price-change anomaly", async () => {
  render(<Recurring />);
  await waitFor(() => expect(screen.getByText("Netflix")).toBeInTheDocument());
  expect(screen.getByText(/price change/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run it (fails — no module)**

Run (PowerShell): `npm --prefix web test -- src/pages/Recurring.test.tsx`
Expected: FAIL (cannot find `./Recurring`).

- [ ] **Step 3: Implement `pages/Recurring.tsx`**

```tsx
import { useEffect, useState, type CSSProperties } from "react";
import { getRecurring, type RecurringAnomaly, type RecurringCharge, type RecurringData } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { formatMoney } from "@/components/money";

const ANOMALY: Record<RecurringAnomaly["type"], { label: string; color: string }> = {
  price_change: { label: "price change", color: "#F59E0B" },
  possibly_canceled: { label: "maybe canceled", color: "var(--fl-muted)" },
  new: { label: "new", color: "var(--persona)" },
};

const badge: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "2px 10px",
  fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--fl-muted)",
};

function ChargeRow({ c }: { c: RecurringCharge }) {
  return (
    <section className="frosted-card" style={{ padding: 18, display: "grid", gridTemplateColumns: "1fr auto", gap: 8, alignItems: "center" }}>
      <div style={{ display: "grid", gap: 6 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span style={{ fontWeight: 700 }}>{c.vendor}</span>
          <span style={badge}>{c.cadence}</span>
          <span style={{ ...badge, color: c.kind === "fixed" ? "var(--fl-muted)" : "#F59E0B" }}>{c.kind}</span>
          {c.category && <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>{c.category}</span>}
        </div>
        <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>next ~{c.next_expected} · {c.count} charges</div>
      </div>
      <div style={{ textAlign: "right" }}>
        <div style={{ fontSize: 20, fontWeight: 800, fontVariantNumeric: "tabular-nums" }}>
          {formatMoney(c.monthly_cost)}<span style={{ fontSize: 12, fontWeight: 500, color: "var(--fl-muted)" }}>/mo</span>
        </div>
        <div style={{ fontSize: 12, color: "var(--fl-muted)", fontVariantNumeric: "tabular-nums" }}>{formatMoney(c.annual_cost)}/yr</div>
        <div title={`${Math.round(c.confidence * 100)}% confidence`} style={{ marginTop: 6, height: 4, width: 80, marginLeft: "auto", borderRadius: 999, background: "var(--fl-line)" }}>
          <div style={{ height: 4, width: `${Math.round(c.confidence * 100)}%`, borderRadius: 999, background: "var(--persona)" }} />
        </div>
      </div>
    </section>
  );
}

export default function Recurring() {
  const { personId, label } = usePersona();
  const [data, setData] = useState<RecurringData | null>(null);

  useEffect(() => {
    let alive = true;
    getRecurring({ personId }).then((d) => alive && setData(d)).catch(() => alive && setData(null));
    return () => { alive = false; };
  }, [personId]);

  if (!data) return <div style={{ color: "var(--fl-muted)" }}>Loading…</div>;

  const { charges, committed, anomalies } = data;

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>Recurring · {label}</h1>
        <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>subscriptions & regular bills</span>
      </header>

      <section className="frosted-card" style={{ padding: 28, display: "flex", alignItems: "baseline", gap: 16, flexWrap: "wrap" }}>
        <div>
          <div style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--fl-muted)" }}>Committed each month</div>
          <div data-testid="committed-total" style={{ fontSize: 40, fontWeight: 800, letterSpacing: "-0.03em" }}>{formatMoney(committed.total)}</div>
          <div style={{ color: "var(--fl-muted)", fontVariantNumeric: "tabular-nums" }}>· {formatMoney(committed.total * 12)} / yr</div>
        </div>
        <div style={{ marginLeft: "auto", textAlign: "right", color: "var(--fl-muted)", fontSize: 13 }}>
          <div>{charges.length} active {charges.length === 1 ? "charge" : "charges"}</div>
          <div>{formatMoney(committed.fixed)} fixed · {formatMoney(committed.variable)} variable</div>
        </div>
      </section>

      {anomalies.length > 0 && (
        <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
          {anomalies.map((a, i) => (
            <span key={`${a.vendor}-${a.type}-${i}`} style={{ ...badge, color: ANOMALY[a.type].color, borderColor: "currentColor" }}>
              {a.vendor} · {ANOMALY[a.type].label}
            </span>
          ))}
        </div>
      )}

      {charges.length === 0 ? (
        <section className="frosted-card" style={{ padding: 32, textAlign: "center", color: "var(--fl-muted)" }}>
          No recurring charges yet. They appear once a vendor bills at a steady cadence three or more times.
        </section>
      ) : (
        <div style={{ display: "grid", gap: 10 }}>
          {charges.map((c) => <ChargeRow key={c.vendor} c={c} />)}
        </div>
      )}
    </div>
  );
}
```
Note: the `committed-total` testid sits on the hero value span (`formatMoney(104.99)` → `$104.99`). Each anomaly chip's text is `"{vendor} · {label}"` (one node) so `getByText("Comcast")` still uniquely matches the charge-row vendor span, while `getByText(/price change/i)` matches the chip.

- [ ] **Step 4: Run it (passes)**

Run (PowerShell): `npm --prefix web test -- src/pages/Recurring.test.tsx`
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
git add web/src/pages/Recurring.tsx web/src/pages/Recurring.test.tsx
git commit -m "feat(web): Recurring page (committed hero + charge list + anomalies)"
```

---

### Task 4: Wire the `/recurring` route

**Files:**
- Modify: `web/src/routes.tsx`

**Interfaces:**
- Consumes: `Recurring` default export (Task 3).

- [ ] **Step 1: Import and swap the placeholder**

In `web/src/routes.tsx`, add near the other page imports:
```tsx
import Recurring from "@/pages/Recurring";
```
Replace:
```tsx
      { path: "recurring", element: <PagePlaceholder title="Recurring" /> },
```
with:
```tsx
      { path: "recurring", element: <Recurring /> },
```

- [ ] **Step 2: Build + full suite**

Run (PowerShell):
```
npm --prefix web run build
npm --prefix web test
```
Expected: build OK; all suites pass.

- [ ] **Step 3: End-to-end smoke (optional)**

Run the API + dev server, click Recurring; confirm the committed hero, anomaly chips, and charge rows render, and persona switch refetches.

- [ ] **Step 4: Commit**

```bash
git add web/src/routes.tsx
git commit -m "feat(web): wire /recurring route"
```

---

## Self-Review

**1. Spec coverage:** GET recurring bundle → Task 1 ✓; vendor-rule transform + Joint=None → Task 1 `_vendor_rules` ✓; natural persona model → Task 1 (uses `get_transactions(person_id)`) ✓; api client + types → Task 2 ✓; committed hero + annual shadow → Task 3 hero section ✓; anomaly chips → Task 3 ✓; charge rows (cadence/kind/cost/next/confidence) → Task 3 `ChargeRow` ✓; empty state → Task 3 ✓; route wired → Task 4 ✓; read-only (no mutations) → page has none ✓. Out-of-scope (managing subs, vendor editing, Net Worth) excluded.

**2. Placeholder scan:** every step has complete code/commands; no TBD/TODO. `PagePlaceholder` is the shipped component being replaced.

**3. Type/interface consistency:** `RecurringData`/`RecurringCharge`/`RecurringAnomaly` (Task 2) consumed unchanged in Task 3; backend bundle keys (`charges`/`committed`/`anomalies`) match the `RecurringData` type and the `recurring_charges`/`committed_monthly`/`recurring_anomalies` outputs; `getRecurring({personId})` signature matches the call site; `_vendor_rules` returns the `(name,[kw])` shape `vendor_of` documents; route element `<Recurring/>` matches the default export.

**Out of scope (later plans):** Net Worth (Plan 7), Goals, Settings, Import wizard, AI Insights, cutover.
