# UI-Fix Deferred Items Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the four items deferred from the Frosted Ledger UI fix (`docs/ui-fix-plan/`): NetWorth per-person comparative split, route-level loading skeletons, `pill`→`Pill` dedup, and lucide-react sidebar icons.

**Architecture:** Frontend is React 19 + TypeScript + Vite, styled with Tailwind v4 utilities over brand `--fl-*`/`--persona*` CSS variables (see `web/src/index.css`) plus a thin primitive layer in `web/src/components/`. Backend is FastAPI (`backend/`) reusing the pandas engine in `modules/`. Charts are hand-rolled SVG (no charting library). All data is local SQLite, keyed by `person_id` (Aviv = id1 owns all data, Ido = id2 empty; Joint = `person_id` omitted).

**Tech Stack:** React 19, TypeScript, Vite 8, Vitest + Testing Library + jsdom, Tailwind v4, lucide-react (already in `web/package.json`); FastAPI + pytest; pandas.

## Global Constraints

- **Node is not on PATH in spawned shells.** Prepend it every shell call: PowerShell `$env:Path = "C:\Users\lahat\node\node-v24.16.0-win-x64;$env:Path"`, then `npx …`. Run frontend commands from `web/`.
- **Backend tests:** `& ".\venv\Scripts\python.exe" -m pytest -q` from repo root. Baseline: **163 passing**.
- **Frontend gates:** `npx tsc -b --noEmit` (clean), `npx vitest run` (baseline **83 passing**), `npx vite build` (green). All three must stay green at every task boundary.
- **Persona colors:** `--persona` may be the Joint gradient — only valid as a `background` fill. For any text/icon/border color use `--persona-solid`.
- **Tokens before bridge:** brand `--fl-*`/`--persona*` vars are declared *before* the shadcn bridge and `@theme inline` in `index.css` (Tailwind v4 forward-pass resolution) — do not reorder.
- **No new charting library.** Reuse `web/src/components/charts/`.
- Persona identity is name-stable: Ido → `you`/blue, Aviv → `spouse`/pink (see `web/src/lib/persona.tsx`).

---

### Task 1: Backend — per-person net-worth split for Joint view

**Files:**
- Modify: `backend/api/networth.py` (the `get_networth` handler)
- Test: `tests/api/test_networth_api.py`

**Interfaces:**
- Consumes: `db.list_accounts(scope)` (returns account dicts incl. `person_id`, nullable), `db.list_people()` (`[{id,name}]`), `analytics.net_worth(accounts) -> {assets,liabilities,net}`.
- Produces: `/api/networth` response gains `split: list | None`. Each item: `{person_id: int|None, name: str, net: float, assets: float, liabilities: float}`. `null` when a single person is selected; present (Joint) when `person_id` is omitted. Shared accounts (`person_id is None`) group under name `"Shared"`.

- [ ] **Step 1: Write the failing test**

Add to `tests/api/test_networth_api.py`:

```python
def test_networth_joint_split_per_person(client, people):
    from modules import database as db
    ido, aviv = people[0]["id"], people[1]["id"]
    db.add_account(ido, "Ido Checking", "checking", True, 1000.0)
    db.add_account(aviv, "Aviv Savings", "savings", True, 4000.0)
    db.add_account(None, "Joint House", "property", True, 200000.0)
    # Joint: split present, one row per owner (+ Shared), nets sum to summary.net
    d = client.get("/api/networth").json()
    assert d["split"] is not None
    by_name = {r["name"]: r["net"] for r in d["split"]}
    assert by_name[people[0]["name"]] == 1000.0
    assert by_name[people[1]["name"]] == 4000.0
    assert by_name["Shared"] == 200000.0
    assert round(sum(r["net"] for r in d["split"]), 2) == round(d["summary"]["net"], 2)
    # Single persona: no split
    d2 = client.get("/api/networth", params={"person_id": ido}).json()
    assert d2["split"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `& ".\venv\Scripts\python.exe" -m pytest tests/api/test_networth_api.py::test_networth_joint_split_per_person -q`
Expected: FAIL — `KeyError: 'split'` (field absent).

- [ ] **Step 3: Implement the split in `get_networth`**

In `backend/api/networth.py`, replace the `get_networth` return with:

```python
@router.get("")
def get_networth(person_id: Optional[int] = None):
    scope = _scope(person_id)
    accounts = db.list_accounts(scope)
    summary = analytics.net_worth(accounts)
    trend_df = analytics.net_worth_trend(db.get_snapshots(scope))
    trend = [] if trend_df.empty else trend_df.to_dict(orient="records")
    delta = round(summary["net"] - trend[-2]["net"], 2) if len(trend) >= 2 else None

    # Joint view: break net worth down by owner (shared accounts → "Shared").
    split = None
    if person_id is None:
        names = {p["id"]: p["name"] for p in db.list_people()}
        groups: dict = {}
        for a in accounts:
            groups.setdefault(a.get("person_id"), []).append(a)
        split = []
        for pid, accs in groups.items():
            s = analytics.net_worth(accs)
            split.append({
                "person_id": pid,
                "name": names.get(pid, "Shared") if pid is not None else "Shared",
                "net": s["net"], "assets": s["assets"], "liabilities": s["liabilities"],
            })
        split.sort(key=lambda r: r["net"], reverse=True)

    return {"summary": summary, "delta": delta, "accounts": accounts, "trend": trend, "split": split}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `& ".\venv\Scripts\python.exe" -m pytest tests/api/test_networth_api.py -q`
Expected: PASS (all networth API tests).

> If `KeyError: 'person_id'` appears, `list_accounts` doesn't surface the column — confirm the `SELECT` in `db.list_accounts` includes `person_id` and add it if missing (it exists on the `accounts` table).

- [ ] **Step 5: Full backend suite + commit**

Run: `& ".\venv\Scripts\python.exe" -m pytest -q` → Expected: 164 passed.

```bash
git add backend/api/networth.py tests/api/test_networth_api.py
git commit -m "feat(api): per-person net-worth split for Joint view"
```

---

### Task 2: Frontend — NetWorth comparative panel (Joint)

**Files:**
- Modify: `web/src/lib/api.ts` (add `NetWorthSplit`, extend `NetWorthData`)
- Modify: `web/src/pages/NetWorth.tsx` (render the comparative panel in Joint)
- Test: `web/src/pages/NetWorth.test.tsx`

**Interfaces:**
- Consumes: `NetWorthData.split` from Task 1.
- Produces: a `Household breakdown` panel (one row per owner, persona-colored, with `Money`) shown only when `personId == null` and `split` has ≥ 1 row.

- [ ] **Step 1: Extend the type in `api.ts`**

Replace the `NetWorthData` type block (around `web/src/lib/api.ts:201`):

```ts
export type NetWorthPoint = { date: string; assets: number; liabilities: number; net: number };
export type NetWorthSplit = { person_id: number | null; name: string; net: number; assets: number; liabilities: number };

export type NetWorthData = {
  summary: { assets: number; liabilities: number; net: number };
  delta: number | null;
  accounts: Account[];
  trend: NetWorthPoint[];
  split: NetWorthSplit[] | null;
};
```

- [ ] **Step 2: Write the failing test**

Add to `web/src/pages/NetWorth.test.tsx` (follow the file's existing mock setup for `@/lib/api` and `@/lib/persona`; set the persona mock's `personId` to `undefined` for Joint). Example assertion-bearing test:

```tsx
test("shows household breakdown rows in Joint view", async () => {
  getNetWorth.mockResolvedValue({
    summary: { assets: 5000, liabilities: 0, net: 5000 }, delta: null, accounts: [], trend: [],
    split: [
      { person_id: 2, name: "Ido", net: 1000, assets: 1000, liabilities: 0 },
      { person_id: 1, name: "Aviv", net: 4000, assets: 4000, liabilities: 0 },
    ],
  });
  render(<NetWorth />);
  const panel = await screen.findByLabelText("Household breakdown");
  expect(within(panel).getByText("Ido")).toBeInTheDocument();
  expect(within(panel).getByText("Aviv")).toBeInTheDocument();
});
```

- [ ] **Step 3: Run test to verify it fails**

Run (from `web/`): `npx vitest run src/pages/NetWorth.test.tsx`
Expected: FAIL — `Unable to find label "Household breakdown"`.

- [ ] **Step 4: Render the panel**

In `web/src/pages/NetWorth.tsx`, destructure `split` from `data` (`const { summary, delta, accounts, trend, split } = data;`) and insert, directly after the summary `</section>`:

```tsx
{personId == null && split && split.length > 0 && (
  <section className="frosted-card" aria-label="Household breakdown" style={{ padding: 20, display: "grid", gap: 10 }}>
    <span style={{ fontSize: 10.5, textTransform: "uppercase", letterSpacing: "0.07em", color: "var(--fl-muted)", fontWeight: 700 }}>
      Household breakdown
    </span>
    {split.map((s) => {
      const color = s.name === "Ido" ? "var(--persona-you)" : s.name === "Aviv" ? "var(--persona-spouse)" : "var(--fl-muted)";
      return (
        <div key={s.name} style={{ display: "flex", alignItems: "center", gap: 10, fontSize: 13 }}>
          <span style={{ width: 9, height: 9, borderRadius: "50%", background: color }} />
          <span style={{ fontWeight: 600 }}>{s.name}</span>
          <span style={{ marginLeft: "auto", fontWeight: 700, fontVariantNumeric: "tabular-nums" }}><Money value={s.net} colored /></span>
        </div>
      );
    })}
  </section>
)}
```

- [ ] **Step 5: Verify, typecheck, commit**

Run (from `web/`): `npx vitest run src/pages/NetWorth.test.tsx` → PASS; then `npx tsc -b --noEmit` → clean.

```bash
git add web/src/lib/api.ts web/src/pages/NetWorth.tsx web/src/pages/NetWorth.test.tsx
git commit -m "feat(web): NetWorth household breakdown panel (Joint)"
```

---

### Task 3: Shared loading skeleton + adopt on data pages

**Files:**
- Create: `web/src/components/loading.tsx`
- Test: `web/src/components/loading.test.tsx`
- Modify: `web/src/pages/Overview.tsx`, `NetWorth.tsx`, `Budgets.tsx`, `Recurring.tsx`, `Goals.tsx`, `Transactions.tsx` (swap each `Loading…` text node)

**Interfaces:**
- Produces: `Loading({ rows?: number })` — renders `role="status"` with an aria-label "Loading" and `rows` (default 3) shimmer bars built on the existing `web/src/components/ui/skeleton.tsx`.

- [ ] **Step 1: Write the failing test**

Create `web/src/components/loading.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { Loading } from "./loading";

test("renders an accessible loading status", () => {
  render(<Loading />);
  expect(screen.getByRole("status")).toHaveAttribute("aria-label", "Loading");
});
```

- [ ] **Step 2: Run to verify it fails**

Run (from `web/`): `npx vitest run src/components/loading.test.tsx`
Expected: FAIL — cannot resolve `./loading`.

- [ ] **Step 3: Implement `loading.tsx`**

Create `web/src/components/loading.tsx`:

```tsx
import { Skeleton } from "@/components/ui/skeleton";

export function Loading({ rows = 3 }: { rows?: number }) {
  return (
    <div role="status" aria-label="Loading" style={{ display: "grid", gap: 12 }}>
      {Array.from({ length: rows }, (_, i) => (
        <Skeleton key={i} className="h-20 w-full rounded-[var(--radius-card)]" />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run to verify it passes**

Run (from `web/`): `npx vitest run src/components/loading.test.tsx`
Expected: PASS.

- [ ] **Step 5: Adopt on the data pages**

In each listed page, replace the early-return loading line — for example in `web/src/pages/Overview.tsx`:

```tsx
// before:  if (!data) return <div style={{ color: "var(--fl-muted)" }}>Loading…</div>;
// after:
if (!data) return <Loading />;
```

Add `import { Loading } from "@/components/loading";` to each page. Apply the identical swap in `NetWorth.tsx`, `Budgets.tsx`, `Recurring.tsx`, `Goals.tsx`, and `Transactions.tsx` (match each file's exact current `Loading…`/`return null` placeholder).

- [ ] **Step 6: Full frontend gates + commit**

Run (from `web/`): `npx tsc -b --noEmit` (clean), `npx vitest run` (all pass), `npx vite build` (green).

```bash
git add web/src/components/loading.tsx web/src/components/loading.test.tsx web/src/pages/Overview.tsx web/src/pages/NetWorth.tsx web/src/pages/Budgets.tsx web/src/pages/Recurring.tsx web/src/pages/Goals.tsx web/src/pages/Transactions.tsx
git commit -m "feat(web): shared loading skeleton across data pages"
```

---

### Task 4: lucide-react sidebar icons

**Files:**
- Modify: `web/src/components/app-sidebar.tsx`

**Interfaces:**
- Consumes: `lucide-react` (already a dependency). Swap the Unicode nav glyphs for icon components; identical layout/sizing.

- [ ] **Step 1: Replace the glyph mapping**

In `web/src/components/app-sidebar.tsx`, import icons and change `NavItem.icon` from `string` to a component. Replace the icon imports/maps:

```tsx
import { LayoutGrid, List, PieChart, RefreshCw, Target, TrendingUp, Tag, Plus, Sparkles, Settings as SettingsIcon } from "lucide-react";
import type { LucideIcon } from "lucide-react";

type NavItem = { to: string; label: string; Icon: LucideIcon; important?: boolean };

const MONEY: NavItem[] = [
  { to: "/", label: "Overview", Icon: LayoutGrid },
  { to: "/transactions", label: "Transactions", Icon: List },
  { to: "/budgets", label: "Budgets", Icon: PieChart },
  { to: "/recurring", label: "Recurring", Icon: RefreshCw },
  { to: "/goals", label: "Goals", Icon: Target },
  { to: "/networth", label: "Net Worth", Icon: TrendingUp },
  { to: "/events", label: "Events", Icon: Tag },
];
const UTILITY: NavItem[] = [
  { to: "/import", label: "Import", Icon: Plus, important: true },
  { to: "/insights", label: "AI Insights", Icon: Sparkles },
  { to: "/settings", label: "Settings", Icon: SettingsIcon },
];
```

- [ ] **Step 2: Render the icon component**

In the `NavGroup` map, replace the glyph `<span>` with:

```tsx
<n.Icon size={16} strokeWidth={2} aria-hidden style={{ flex: "none", opacity: 0.85 }} />
```

- [ ] **Step 3: Typecheck + build + commit**

Run (from `web/`): `npx tsc -b --noEmit` (clean), `npx vitest run` (83 pass — sidebar has no test, but confirm no regressions), `npx vite build` (green).

```bash
git add web/src/components/app-sidebar.tsx
git commit -m "feat(web): lucide-react sidebar nav icons"
```

---

### Task 5: `pill` CSSProperties → `Pill` primitive dedup

**Files:**
- Modify: `web/src/pages/Transactions.tsx`, `NetWorth.tsx`, `Budgets.tsx`, `Goals.tsx`, `Recurring.tsx`, `Events.tsx`, `Settings.tsx`, `Import.tsx`
- Reference: `web/src/components/ui/pill.tsx` (`Pill`, polymorphic via `as`, `active` prop)

**Interfaces:**
- Consumes: `Pill` (`<Pill>`, `<Pill as="select">`, etc.). Pure refactor — **no visual change intended**; tests assert text/role/testid, not class names.

- [ ] **Step 1: Convert one page (Goals) as the pattern**

In `web/src/pages/Goals.tsx`: remove the local `const pill: CSSProperties = {…}` and its `type CSSProperties` import if now unused. Replace button usages:

```tsx
// before: <button onClick={submit} style={{ ...pill, fontWeight: 700, color: "var(--persona-solid)" }}>Add goal</button>
// after:
<Pill onClick={submit} style={{ fontWeight: 700, color: "var(--persona-solid)" }}>Add goal</Pill>
```

For inputs/selects that used `style={pill}`, give them `className` from the same source: `<input className="…" />` is overkill — instead keep those as bare inputs styled by the existing form rules, or wrap with `<Pill as="input" …/>`. Import `import { Pill } from "@/components/ui/pill";`.

- [ ] **Step 2: Run Goals test**

Run (from `web/`): `npx vitest run src/pages/Goals.test.tsx`
Expected: PASS (behavior unchanged).

- [ ] **Step 3: Repeat for the remaining pages**

Apply the same mechanical conversion to `Transactions.tsx`, `NetWorth.tsx`, `Budgets.tsx`, `Recurring.tsx`, `Events.tsx`, `Settings.tsx`, `Import.tsx`. After each file, run that page's `*.test.tsx`.

- [ ] **Step 4: Full gates + commit**

Run (from `web/`): `npx tsc -b --noEmit` (clean — watch for now-unused `CSSProperties` imports), `npx vitest run` (83 pass), `npx vite build` (green).

```bash
git add web/src/pages/Transactions.tsx web/src/pages/NetWorth.tsx web/src/pages/Budgets.tsx web/src/pages/Goals.tsx web/src/pages/Recurring.tsx web/src/pages/Events.tsx web/src/pages/Settings.tsx web/src/pages/Import.tsx
git commit -m "refactor(web): replace per-page pill objects with the Pill primitive"
```

---

## Self-Review

- **Coverage:** Task 1+2 = NetWorth per-person comparative split; Task 3 = route-level loading skeletons; Task 4 = lucide icons; Task 5 = pill dedup. All four deferred items covered.
- **Types:** `NetWorthSplit`/`NetWorthData.split` (Task 2) match the backend payload shape from Task 1 (`person_id`, `name`, `net`, `assets`, `liabilities`). `Loading({rows})` (Task 3) used consistently. `NavItem.Icon: LucideIcon` (Task 4) replaces the old `icon: string`.
- **Ordering:** Task 2 depends on Task 1 (backend field first). Tasks 3–5 are independent and can run in any order.
- **Risk note:** Task 5 is the highest-churn / lowest-value; if time-boxed, ship Tasks 1–4 and treat Task 5 as optional cleanup.
