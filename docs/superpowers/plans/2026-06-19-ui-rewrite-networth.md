# UI Rewrite — Plan 8: Net Worth Page Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `/networth` placeholder with a persona-scoped page showing net worth (assets − liabilities) with a delta and trend, plus a per-account ledger with inline balance editing, add, and delete — backed by a new thin FastAPI networth router over the engine's existing accounts/net-worth functions.

**Architecture:** `backend/api/networth.py` returns one bundle from `db.list_accounts` + `analytics.net_worth` + `analytics.net_worth_trend(db.get_snapshots)`, and exposes accounts add/update-balance/delete via `db.add_account`/`update_account_balance`/`delete_account`. `lib/api.ts` gains the types + `getNetWorth`/`addAccount`/`updateAccountBalance`/`deleteAccount`. `pages/NetWorth.tsx` renders a hero + SVG sparkline + account ledger, refetching after each mutation.

**Tech Stack:** FastAPI + pytest (TestClient, temp-DB fixtures); React 18 + TS, Vitest + Testing Library.

## Working Context
- Worktree `.claude/worktrees/ui-rewrite`, branch `feature/ui-rewrite`. Depends on Plans 1–7.
- **npm/npx via PowerShell**, prepend the portable Node to PATH first:
  `$env:Path = "C:\Users\lahat\node\node-v24.16.0-win-x64;" + $env:Path`. Then `npm --prefix web ...` from the worktree root.
- **pytest via** `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest ...` from the worktree root.
- Design doc: `docs/superpowers/specs/2026-06-19-networth-page-design.md` (engine design: `2026-06-17-net-worth-design.md`).
- Engine (do NOT modify): `db.list_accounts(person_id="all")`; `db.add_account(person_id, name, kind, is_asset, balance)` → id (+ today snapshot); `db.update_account_balance(account_id, balance, snapshot_date=None)`; `db.delete_account(account_id)` (cascades snapshots); `db.get_snapshots(person_id="all")` → snapshots tagged is_asset; `db.write_snapshot(account_id, snap_date, balance)`; `analytics.net_worth(accounts)` → `{assets, liabilities, net}`; `analytics.net_worth_trend(snapshots)` → **pandas DataFrame** `[date, assets, liabilities, net]` (empty frame when no snapshots). Account dict: `{id, person_id, name, kind, is_asset(0|1), balance, updated_at}`.

## Global Constraints (carried from the spec)
- Local-only; reuse the engine; do NOT modify `modules/*.py`. (spec §1)
- **Persona mapping:** You→people[0], Spouse→people[1] → that person; Joint (`person_id` omitted) → router maps to `"all"`. Account added from Joint → `person_id` null (shared). (design §Persona)
- `balance` is a positive magnitude; `is_asset` decides the sign. `is_asset` derived from kind in the add form (`credit_card`/`loan` → liability, else asset). (engine design)
- Frosted Ledger: `--persona` accent, `--pos`/`--neg`, tabular numerals, 18px cards. (spec §3)

## File Structure (this plan)
```
backend/schemas.py              # MODIFY: + AccountCreate, AccountBalanceUpdate
backend/api/networth.py         # CREATE: GET bundle + accounts POST/PATCH/DELETE
backend/main.py                 # MODIFY: register networth router
tests/api/test_networth_api.py  # CREATE
web/src/lib/api.ts              # MODIFY: + types + 4 functions
web/src/lib/api.test.ts         # MODIFY: + 4 tests
web/src/pages/NetWorth.tsx      # CREATE
web/src/pages/NetWorth.test.tsx # CREATE
web/src/routes.tsx              # MODIFY: /networth -> <NetWorth/>
```

---

### Task 1: Net Worth API router (backend)

**Files:**
- Modify: `backend/schemas.py`, `backend/main.py`
- Create: `backend/api/networth.py`, `tests/api/test_networth_api.py`

**Interfaces:**
- Consumes: `db.list_accounts/add_account/update_account_balance/delete_account/get_snapshots`, `analytics.net_worth/net_worth_trend`.
- Produces: `GET /api/networth?person_id=` bundle; `POST/PATCH/DELETE /api/networth/accounts[...]`.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_networth_api.py`:
```python
def test_networth_summary(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.add_account(you, "Checking", "checking", 1, 5000.0)
    db.add_account(you, "Visa", "credit_card", 0, 1200.0)

    data = client.get("/api/networth", params={"person_id": you}).json()
    assert data["summary"] == {"assets": 5000.0, "liabilities": 1200.0, "net": 3800.0}
    assert len(data["accounts"]) == 2


def test_add_account_via_api(client, people):
    you = people[0]["id"]
    r = client.post("/api/networth/accounts", json={
        "person_id": you, "name": "Vanguard", "kind": "investment",
        "is_asset": True, "balance": 25000})
    assert r.status_code == 200
    data = client.get("/api/networth", params={"person_id": you}).json()
    assert any(a["name"] == "Vanguard" for a in data["accounts"])
    assert data["summary"]["assets"] == 25000.0


def test_update_account_balance_via_api(client, people):
    from modules import database as db
    you = people[0]["id"]
    aid = db.add_account(you, "Savings", "savings", 1, 1000.0)
    r = client.patch(f"/api/networth/accounts/{aid}", json={"balance": 1500})
    assert r.status_code == 200
    data = client.get("/api/networth", params={"person_id": you}).json()
    assert data["summary"]["net"] == 1500.0


def test_delete_account_via_api(client, people):
    from modules import database as db
    you = people[0]["id"]
    aid = db.add_account(you, "Temp", "other", 1, 100.0)
    client.delete(f"/api/networth/accounts/{aid}")
    data = client.get("/api/networth", params={"person_id": you}).json()
    assert data["accounts"] == []


def test_trend_and_delta(client, people):
    from modules import database as db
    you = people[0]["id"]
    aid = db.add_account(you, "Brokerage", "investment", 1, 10000.0)  # snapshot today
    db.write_snapshot(aid, "2026-01-01", 8000.0)                       # older snapshot

    data = client.get("/api/networth", params={"person_id": you}).json()
    assert len(data["trend"]) == 2
    assert data["trend"][0]["net"] == 8000.0
    assert data["delta"] == 2000.0  # current net 10000 - prior trend date 8000
```

- [ ] **Step 2: Run it (fails — no route)**

Run: `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api/test_networth_api.py -q`
Expected: FAIL (404).

- [ ] **Step 3: Add the schemas**

In `backend/schemas.py`, append:
```python
class AccountCreate(BaseModel):
    person_id: Optional[int] = None
    name: str
    kind: str
    is_asset: bool
    balance: float = 0


class AccountBalanceUpdate(BaseModel):
    balance: float
```

- [ ] **Step 4: Create the router**

Create `backend/api/networth.py`:
```python
from typing import Optional

from fastapi import APIRouter

from modules import database as db
from modules import analytics
from backend.schemas import AccountCreate, AccountBalanceUpdate

router = APIRouter(prefix="/networth", tags=["networth"])


def _scope(person_id: Optional[int]):
    """Persona -> engine scope: a real person id, or 'all' for Joint."""
    return person_id if person_id is not None else "all"


@router.get("")
def get_networth(person_id: Optional[int] = None):
    scope = _scope(person_id)
    accounts = db.list_accounts(scope)
    summary = analytics.net_worth(accounts)
    trend_df = analytics.net_worth_trend(db.get_snapshots(scope))
    trend = [] if trend_df.empty else trend_df.to_dict(orient="records")
    delta = round(summary["net"] - trend[-2]["net"], 2) if len(trend) >= 2 else None
    return {"summary": summary, "delta": delta, "accounts": accounts, "trend": trend}


@router.post("/accounts")
def create_account(body: AccountCreate):
    aid = db.add_account(body.person_id, body.name, body.kind, body.is_asset, body.balance)
    return {"ok": True, "id": aid}


@router.patch("/accounts/{account_id}")
def update_account(account_id: int, body: AccountBalanceUpdate):
    db.update_account_balance(account_id, body.balance)
    return {"ok": True}


@router.delete("/accounts/{account_id}")
def remove_account(account_id: int):
    db.delete_account(account_id)
    return {"ok": True}
```

- [ ] **Step 5: Register the router**

In `backend/main.py`, change the import to include `networth`:
```python
from backend.api import budgets, goals, networth, overview, people, recurring, transactions
```
and add after the `goals` include:
```python
    app.include_router(networth.router, prefix="/api")
```

- [ ] **Step 6: Run it (passes)**

Run: `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api/test_networth_api.py -q`
Expected: 5 passed.

- [ ] **Step 7: Full API suite (no regressions)**

Run: `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api -q`
Expected: all pass (30 total: 25 prior + 5 new).

- [ ] **Step 8: Commit**

```bash
git add backend/api/networth.py backend/schemas.py backend/main.py tests/api/test_networth_api.py
git commit -m "feat(api): net worth router (summary + trend + accounts CRUD)"
```

---

### Task 2: Net Worth API client (frontend)

**Files:**
- Modify: `web/src/lib/api.ts`, `web/src/lib/api.test.ts`

**Interfaces:**
- Consumes: `apiGet`, `apiSend` (Plan 3).
- Produces: `type Account`, `type NetWorthPoint`, `type NetWorthData`; `getNetWorth`, `addAccount`, `updateAccountBalance`, `deleteAccount`.

- [ ] **Step 1: Write the failing tests**

In `web/src/lib/api.test.ts`, extend the import line to add the four functions:
```ts
import { getOverview, getTransactions, updateTransaction, getBudgets, setBudget, deleteBudget, getRecurring, getGoals, addGoal, updateGoalSaved, deleteGoal, getNetWorth, addAccount, updateAccountBalance, deleteAccount } from "./api";
```
Append:
```ts
test("getNetWorth builds /api/networth with person_id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ summary: { assets: 0, liabilities: 0, net: 0 }, delta: null, accounts: [], trend: [] }) });
  vi.stubGlobal("fetch", fetchMock);
  await getNetWorth({ personId: 1 });
  expect(fetchMock.mock.calls[0][0]).toBe("/api/networth?person_id=1");
});

test("addAccount POSTs derived is_asset", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true, id: 1 }) });
  vi.stubGlobal("fetch", fetchMock);
  await addAccount({ personId: 1, name: "Vanguard", kind: "investment", isAsset: true, balance: 25000 });
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/networth/accounts");
  expect(init.method).toBe("POST");
  expect(JSON.parse(init.body as string)).toEqual({ person_id: 1, name: "Vanguard", kind: "investment", is_asset: true, balance: 25000 });
});

test("updateAccountBalance PATCHes balance", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await updateAccountBalance(3, 1500);
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/networth/accounts/3");
  expect(init.method).toBe("PATCH");
  expect(JSON.parse(init.body as string)).toEqual({ balance: 1500 });
});

test("deleteAccount DELETEs by id", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ ok: true }) });
  vi.stubGlobal("fetch", fetchMock);
  await deleteAccount(3);
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
  expect(url).toBe("/api/networth/accounts/3");
  expect(init.method).toBe("DELETE");
});
```

- [ ] **Step 2: Run it (fails)**

Run (PowerShell, Node on PATH): `npm --prefix web test -- src/lib/api.test.ts`
Expected: FAIL (functions not exported).

- [ ] **Step 3: Implement in `lib/api.ts`**

Append at the end of the file:
```ts
export type Account = {
  id: number;
  person_id: number | null;
  name: string;
  kind: string;
  is_asset: number;
  balance: number;
  updated_at: string;
};

export type NetWorthPoint = { date: string; assets: number; liabilities: number; net: number };

export type NetWorthData = {
  summary: { assets: number; liabilities: number; net: number };
  delta: number | null;
  accounts: Account[];
  trend: NetWorthPoint[];
};

export const getNetWorth = (p: { personId?: number }) =>
  apiGet<NetWorthData>("/networth", { person_id: p.personId });

export const addAccount = (a: { personId?: number; name: string; kind: string; isAsset: boolean; balance: number }) =>
  apiSend<{ ok: boolean; id: number }>("POST", "/networth/accounts", {
    person_id: a.personId, name: a.name, kind: a.kind, is_asset: a.isAsset, balance: a.balance,
  });

export const updateAccountBalance = (id: number, balance: number) =>
  apiSend<{ ok: boolean }>("PATCH", `/networth/accounts/${id}`, { balance });

export const deleteAccount = (id: number) =>
  apiSend<{ ok: boolean }>("DELETE", `/networth/accounts/${id}`);
```

- [ ] **Step 4: Run it (passes)**

Run (PowerShell): `npm --prefix web test -- src/lib/api.test.ts`
Expected: 17 passed.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/api.ts web/src/lib/api.test.ts
git commit -m "feat(web): net worth API client"
```

---

### Task 3: Net Worth page

**Files:**
- Create: `web/src/pages/NetWorth.tsx`, `web/src/pages/NetWorth.test.tsx`

**Interfaces:**
- Consumes: `getNetWorth`, `addAccount`, `updateAccountBalance`, `deleteAccount`, `Account`, `NetWorthData` (Task 2); `usePersona()`, `Money`, `formatMoney`.
- Produces: `export default function NetWorth()` — the route element for Task 4.

- [ ] **Step 1: Write the failing test**

Create `web/src/pages/NetWorth.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";

const addAccount = vi.fn().mockResolvedValue({ ok: true, id: 9 });
const updateAccountBalance = vi.fn().mockResolvedValue({ ok: true });
const deleteAccount = vi.fn().mockResolvedValue({ ok: true });
const getNetWorth = vi.fn().mockResolvedValue({
  summary: { assets: 30000, liabilities: 5000, net: 25000 },
  delta: 2000,
  accounts: [
    { id: 1, person_id: 1, name: "Vanguard", kind: "investment", is_asset: 1, balance: 30000, updated_at: "2026-06-19" },
    { id: 2, person_id: 1, name: "Visa", kind: "credit_card", is_asset: 0, balance: 5000, updated_at: "2026-06-19" },
  ],
  trend: [
    { date: "2026-01-01", assets: 28000, liabilities: 5000, net: 23000 },
    { date: "2026-06-19", assets: 30000, liabilities: 5000, net: 25000 },
  ],
});

vi.mock("@/lib/persona", () => ({
  usePersona: () => ({
    persona: "you", personId: 1, label: "Ada",
    people: [{ id: 1, name: "Ada" }, { id: 2, name: "Mara" }], setPersona: () => {},
  }),
}));
vi.mock("@/lib/api", () => ({
  getNetWorth: (...a: unknown[]) => getNetWorth(...a),
  addAccount: (...a: unknown[]) => addAccount(...a),
  updateAccountBalance: (...a: unknown[]) => updateAccountBalance(...a),
  deleteAccount: (...a: unknown[]) => deleteAccount(...a),
}));

import NetWorth from "./NetWorth";

afterEach(() => { addAccount.mockClear(); updateAccountBalance.mockClear(); deleteAccount.mockClear(); });

test("renders the net worth total and accounts", async () => {
  render(<NetWorth />);
  await waitFor(() => expect(screen.getByTestId("networth-total")).toHaveTextContent("$25,000.00"));
  expect(screen.getByText("Vanguard")).toBeInTheDocument();
  expect(screen.getByText("Visa")).toBeInTheDocument();
});

test("editing a balance calls updateAccountBalance", async () => {
  render(<NetWorth />);
  await waitFor(() => expect(screen.getByText("Vanguard")).toBeInTheDocument());
  const bal = screen.getByDisplayValue("30000");
  await userEvent.clear(bal);
  await userEvent.type(bal, "31000");
  await userEvent.tab();
  expect(updateAccountBalance).toHaveBeenCalledWith(1, 31000);
});

test("removing an account calls deleteAccount", async () => {
  render(<NetWorth />);
  await waitFor(() => expect(screen.getByText("Vanguard")).toBeInTheDocument());
  const remove = screen.getAllByRole("button", { name: /remove/i });
  await userEvent.click(remove[0]);
  expect(deleteAccount).toHaveBeenCalledWith(1);
});
```

- [ ] **Step 2: Run it (fails — no module)**

Run (PowerShell): `npm --prefix web test -- src/pages/NetWorth.test.tsx`
Expected: FAIL (cannot find `./NetWorth`).

- [ ] **Step 3: Implement `pages/NetWorth.tsx`**

```tsx
import { useCallback, useEffect, useState, type CSSProperties } from "react";
import { getNetWorth, addAccount, updateAccountBalance, deleteAccount, type Account, type NetWorthData, type NetWorthPoint } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { Money, formatMoney } from "@/components/money";

const KINDS = ["checking", "savings", "investment", "property", "credit_card", "loan", "other"];
const LIABILITY_KINDS = new Set(["credit_card", "loan"]);
const isAssetKind = (kind: string) => !LIABILITY_KINDS.has(kind);

const pill: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "6px 12px",
  fontSize: 13, background: "transparent", color: "var(--fl-ink)",
};
const badge: CSSProperties = {
  border: "1px solid var(--fl-line)", borderRadius: 999, padding: "2px 10px",
  fontSize: 11, textTransform: "uppercase", letterSpacing: "0.05em", color: "var(--fl-muted)",
};

function Sparkline({ points }: { points: NetWorthPoint[] }) {
  const W = 520, H = 64, P = 4;
  const nets = points.map((p) => p.net);
  const min = Math.min(...nets), max = Math.max(...nets);
  const span = max - min || 1;
  const coords = points.map((p, i) => {
    const x = P + (i / (points.length - 1)) * (W - 2 * P);
    const y = H - P - ((p.net - min) / span) * (H - 2 * P);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });
  return (
    <svg viewBox={`0 0 ${W} ${H}`} width="100%" height={H} role="img" aria-label="Net worth trend" style={{ display: "block" }}>
      <polyline fill="none" stroke="var(--persona)" strokeWidth={2} strokeLinejoin="round" strokeLinecap="round" points={coords.join(" ")} />
    </svg>
  );
}

function AccountRow({ a, onSave, onRemove }: {
  a: Account; onSave: (a: Account, v: string) => void; onRemove: (a: Account) => void;
}) {
  const asset = !!a.is_asset;
  return (
    <section className="frosted-card" style={{ padding: 16, display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
      <span style={{ fontWeight: 700 }}>{a.name}</span>
      <span style={badge}>{a.kind.replace("_", " ")}</span>
      <span style={{ ...badge, color: asset ? "var(--pos)" : "var(--neg)", borderColor: "currentColor" }}>
        {asset ? "asset" : "liability"}
      </span>
      <span style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
        <input
          type="number"
          defaultValue={a.balance}
          aria-label={`Balance for ${a.name}`}
          onBlur={(e) => onSave(a, e.target.value)}
          style={{ ...pill, width: 130, padding: "4px 10px", textAlign: "right" }}
        />
        <button
          onClick={() => onRemove(a)}
          aria-label={`Remove ${a.name} account`}
          style={{ border: "none", background: "none", color: "var(--fl-muted)", cursor: "pointer", fontSize: 16, lineHeight: 1 }}
        >
          ✕
        </button>
      </span>
    </section>
  );
}

export default function NetWorth() {
  const { personId, label } = usePersona();
  const [data, setData] = useState<NetWorthData | null>(null);
  const [adding, setAdding] = useState(false);
  const [name, setName] = useState("");
  const [kind, setKind] = useState("checking");
  const [balance, setBalance] = useState("");

  const load = useCallback(
    () => getNetWorth({ personId }).then(setData).catch(() => setData(null)),
    [personId],
  );
  useEffect(() => { load(); }, [load]);

  const commitBalance = (a: Account, value: string) => {
    const next = Number(value);
    if (Number.isFinite(next) && next >= 0 && next !== a.balance) {
      updateAccountBalance(a.id, next).then(load);
    }
  };
  const remove = (a: Account) => deleteAccount(a.id).then(load);
  const submit = () => {
    const bal = Number(balance);
    const nm = name.trim();
    if (nm && Number.isFinite(bal) && bal >= 0) {
      addAccount({ personId, name: nm, kind, isAsset: isAssetKind(kind), balance: bal }).then(() => {
        setName(""); setKind("checking"); setBalance(""); setAdding(false); load();
      });
    }
  };

  if (!data) return <div style={{ color: "var(--fl-muted)" }}>Loading…</div>;

  const { summary, delta, accounts, trend } = data;
  const deltaColor = delta == null ? "var(--fl-muted)" : delta > 0 ? "var(--pos)" : delta < 0 ? "var(--neg)" : "var(--fl-muted)";

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "baseline", gap: 12 }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>Net Worth · {label}</h1>
        <span style={{ color: "var(--fl-muted)", fontSize: 13 }}>assets minus liabilities</span>
      </header>

      <section className="frosted-card" style={{ padding: 28, display: "grid", gap: 12 }}>
        <div style={{ display: "flex", alignItems: "baseline", gap: 16, flexWrap: "wrap" }}>
          <div>
            {delta != null && (
              <div style={{ fontSize: 13, fontWeight: 700, color: deltaColor }}>
                {delta > 0 ? "▲" : delta < 0 ? "▼" : ""} {formatMoney(Math.abs(delta))} since last snapshot
              </div>
            )}
            <div data-testid="networth-total" style={{ fontSize: 44, fontWeight: 800, letterSpacing: "-0.03em" }}>
              {formatMoney(summary.net)}
            </div>
          </div>
          <div style={{ marginLeft: "auto", textAlign: "right", color: "var(--fl-muted)", fontSize: 13, fontVariantNumeric: "tabular-nums" }}>
            <div><Money value={summary.assets} /> assets</div>
            <div><Money value={summary.liabilities} /> liabilities</div>
          </div>
        </div>
        {trend.length >= 2
          ? <Sparkline points={trend} />
          : <div style={{ color: "var(--fl-muted)", fontSize: 13 }}>Add a second snapshot to see a trend.</div>}
      </section>

      {accounts.length === 0 && !adding && (
        <section className="frosted-card" style={{ padding: 32, textAlign: "center", color: "var(--fl-muted)" }}>
          No accounts yet. Add one to start tracking net worth.
        </section>
      )}

      <div style={{ display: "grid", gap: 10 }}>
        {accounts.map((a) => <AccountRow key={a.id} a={a} onSave={commitBalance} onRemove={remove} />)}
      </div>

      {adding ? (
        <section className="frosted-card" style={{ padding: 20, display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center" }}>
          <input placeholder="Account name" value={name} onChange={(e) => setName(e.target.value)} style={pill} />
          <select aria-label="Kind" value={kind} onChange={(e) => setKind(e.target.value)} style={pill}>
            {KINDS.map((k) => <option key={k} value={k}>{k.replace("_", " ")}</option>)}
          </select>
          <input type="number" placeholder="Balance" value={balance} onChange={(e) => setBalance(e.target.value)} style={{ ...pill, width: 140 }} />
          <span style={{ ...badge, color: isAssetKind(kind) ? "var(--pos)" : "var(--neg)", borderColor: "currentColor" }}>
            {isAssetKind(kind) ? "asset" : "liability"}
          </span>
          <button onClick={submit} style={{ ...pill, fontWeight: 700, color: "var(--persona)" }}>Add account</button>
          <button onClick={() => setAdding(false)} style={{ ...pill, color: "var(--fl-muted)" }}>Cancel</button>
        </section>
      ) : (
        <button onClick={() => setAdding(true)} style={{ ...pill, justifySelf: "start", color: "var(--persona)" }}>＋ Add an account</button>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Run it (passes)**

Run (PowerShell): `npm --prefix web test -- src/pages/NetWorth.test.tsx`
Expected: 3 passed.

- [ ] **Step 5: Full web suite + build**

Run (PowerShell):
```
npm --prefix web test
npm --prefix web run build
```
Expected: all suites pass (33 tests across 9 files); build OK.

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/NetWorth.tsx web/src/pages/NetWorth.test.tsx
git commit -m "feat(web): Net Worth page (hero + delta + sparkline + accounts CRUD)"
```

---

### Task 4: Wire the `/networth` route

**Files:**
- Modify: `web/src/routes.tsx`

- [ ] **Step 1: Import and swap the placeholder**

In `web/src/routes.tsx`, add near the other page imports:
```tsx
import NetWorth from "@/pages/NetWorth";
```
Replace:
```tsx
      { path: "networth", element: <PagePlaceholder title="Net Worth" /> },
```
with:
```tsx
      { path: "networth", element: <NetWorth /> },
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
git commit -m "feat(web): wire /networth route"
```

---

## Self-Review

**1. Spec coverage:** GET bundle (summary+delta+accounts+trend) → Task 1 `get_networth` ✓; persona You/Spouse→int, Joint→"all" → Task 1 `_scope` ✓; delta = net − prior trend net → Task 1 ✓; accounts add (is_asset bool)/update-balance/delete → Task 1 ✓; api client + types → Task 2 ✓; hero + delta color + assets/liabilities → Task 3 ✓; sparkline when ≥2 trend points, caption otherwise → Task 3 `Sparkline` ✓; account ledger with inline balance edit + delete → Task 3 `AccountRow` ✓; add form with kind→is_asset derivation + active-persona owner → Task 3 ✓; empty state → Task 3 ✓; route wired → Task 4 ✓; refetch after mutation → Task 3 `load()` ✓.

**2. Placeholder scan:** every step has complete code/commands; no TBD/TODO. `PagePlaceholder` is the shipped component being replaced.

**3. Type/interface consistency:** `Account`/`NetWorthPoint`/`NetWorthData` (Task 2) consumed unchanged in Task 3; backend bundle keys (`summary`/`delta`/`accounts`/`trend`) and account fields (`is_asset` 0|1, etc.) match the types and the engine outputs; `net_worth_trend` DataFrame → records via `to_dict` (empty frame → `[]`); `addAccount`/`updateAccountBalance`/`deleteAccount` signatures match call sites and the `AccountCreate`/`AccountBalanceUpdate` bodies; route element `<NetWorth/>` matches the default export. Edit-balance test relies on `defaultValue={a.balance}` rendering `30000` and `31000 !== 30000` passing the change guard; delete test uses `aria-label="Remove {name} account"`.

**Out of scope (later plans):** Import wizard (incl. statement auto-refresh), AI Insights, Settings, cutover.
