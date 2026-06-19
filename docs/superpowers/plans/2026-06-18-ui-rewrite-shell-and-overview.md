# UI Rewrite — Plan 3: App Shell, Persona, Theme & Overview Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the Plan 2 scaffold into a navigable app: a left-sidebar shell with client-side routing, a persona switch (You / Spouse / Joint) that recolors the accent and scopes data, a dark-mode toggle, a typed API client, and the **Overview** dashboard wired to the live `/api/overview` — all covered by Vitest component tests.

**Architecture:** A small set of cross-cutting providers (`PersonaProvider`, `ThemeProvider`) wrap a `react-router` layout (`AppLayout` = sidebar + `<Outlet/>`). A typed `lib/api.ts` fetch client talks to `/api/*` (proxied in dev by Plan 2's Vite config). The persona maps to the backend `person_id` query param. Overview is the first real page; every other nav route renders a shared `PagePlaceholder` until its own plan lands.

**Tech Stack:** React 18, TypeScript, react-router-dom v6, Tailwind v4 + shadcn/ui (from Plan 2), Vitest + Testing Library + jsdom.

## Working Context
- Worktree `.claude/worktrees/ui-rewrite`, branch `feature/ui-rewrite`. Depends on **Plan 2 completed** (Node installed; `web/` scaffolded; `backend/` package; shadcn slate + Frosted Ledger tokens in `web/src/index.css`; `@/` alias).
- Node commands: run npm/npx via **PowerShell**, not the Bash tool — the Bash tool cannot resolve `node` on PATH in this environment (confirmed in Plan 2 Tasks 4–5); PowerShell resolves it fine. Use `npm --prefix web ...`. Keep all npm/npx steps non-interactive (a prompt will hang a subagent — report BLOCKED with the prompt rather than waiting).
- Python (for the API the SPA calls in the dev-proxy sanity check): `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe`.
- shadcn components already added in Plan 2: `button card separator badge avatar dropdown-menu tabs skeleton tooltip sonner`. This plan adds `sidebar` (+ its peer deps) via the shadcn CLI/MCP.

## Global Constraints (carried from the spec)
- Local-only, no auth/cloud/analytics. Reuse the engine; do not modify `modules/*.py`. (spec §1)
- Persona model = `You | Spouse | Joint`; `Joint` = all people merged → omit `person_id` (backend treats `person_id=None` as everyone). You = `people[0]`, Spouse = `people[1]` from `GET /api/people` (renameable; show their live names). (spec §4, §9)
- Frosted Ledger identity: persona accent swaps the `--persona` CSS var (You `#3B82F6`, Spouse `#EC4899`, Joint = blue→pink seam). Slate base; soft 18px cards; big bold numbers; tabular numerals. (spec §3)
- Dark mode via the `.dark` class on `<html>`, toggled in the top bar; tokens already defined in Plan 2. (spec §3, §13)
- Left-sidebar navigation, persona switch pinned at top; nav order: Overview · Transactions · Budgets · Recurring · Goals · Net Worth · ＋ Import · AI Insights · Settings. (spec §4)

## File Structure (created this plan)
```
web/src/
  lib/api.ts            # typed fetch client (base "/api")
  lib/persona.tsx       # PersonaProvider + usePersona()
  lib/theme.tsx         # ThemeProvider + useTheme()
  components/app-sidebar.tsx   # left nav with persona switch + theme toggle
  components/page-placeholder.tsx
  components/money.tsx   # <Money/> + formatMoney() (tabular, signed, colored)
  routes.tsx            # route table
  pages/Overview.tsx
  pages/Overview.test.tsx
  lib/persona.test.tsx
  App.tsx               # replaced: providers + RouterProvider
  main.tsx              # ensure providers/router mount
```

---

### Task 1: Install routing + test toolchain

**Files:**
- Modify: `web/package.json` (deps), `web/vite.config.ts` (vitest config), create `web/src/test/setup.ts`

**Interfaces:**
- Produces: `npm --prefix web test` runs Vitest (jsdom env, jest-dom matchers); `react-router-dom` available.

- [ ] **Step 1: Install deps**

```bash
npm --prefix web install react-router-dom
npm --prefix web install -D vitest @testing-library/react @testing-library/jest-dom @testing-library/user-event jsdom
```

- [ ] **Step 2: Vitest test setup file**

Create `web/src/test/setup.ts`:
```ts
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 3: Wire Vitest into Vite config**

In `web/vite.config.ts`, add a `test` block to the `defineConfig` object (keep the existing `plugins`/`resolve`/`server`):
```ts
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
  },
```
At the top of the file, change the import so the `test` key type-checks:
```ts
/// <reference types="vitest" />
import { defineConfig } from "vite";
```

- [ ] **Step 4: Add the test script**

In `web/package.json` `"scripts"`, add: `"test": "vitest run"` and `"test:watch": "vitest"`.

- [ ] **Step 5: Smoke test passes**

Create `web/src/test/smoke.test.ts`:
```ts
import { expect, test } from "vitest";
test("toolchain works", () => { expect(1 + 1).toBe(2); });
```
Run:
```bash
npm --prefix web test
```
Expected: 1 passed. Then delete `web/src/test/smoke.test.ts`.

- [ ] **Step 6: Commit**

```bash
git add web/package.json web/package-lock.json web/vite.config.ts web/src/test/setup.ts
git commit -m "chore(web): add react-router + vitest/testing-library toolchain"
```

---

### Task 2: Typed API client (`lib/api.ts`)

**Files:**
- Create: `web/src/lib/api.ts`, `web/src/lib/api.test.ts`

**Interfaces:**
- Produces:
  - `type Person = { id: number; name: string }`
  - `type Overview = { month: string | null; months: string[]; income: number; spend: number; net: number; savings_rate: number | null; complete: boolean; by_category: Record<string, number> }`
  - `getPeople(): Promise<Person[]>`
  - `getOverview(p: { personId?: number; month?: string }): Promise<Overview>`
  - low-level `apiGet<T>(path, params?)` used by later plans.

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/api.test.ts`:
```ts
import { afterEach, expect, test, vi } from "vitest";
import { getOverview } from "./api";

afterEach(() => vi.restoreAllMocks());

test("getOverview builds /api/overview with person_id+month and returns JSON", async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ month: "2026-05", months: ["2026-05"], income: 10, spend: 4, net: 6, savings_rate: 0.6, complete: true, by_category: { Rent: 4 } }),
  });
  vi.stubGlobal("fetch", fetchMock);

  const d = await getOverview({ personId: 1, month: "2026-05" });

  const url = fetchMock.mock.calls[0][0] as string;
  expect(url).toBe("/api/overview?person_id=1&month=2026-05");
  expect(d.net).toBe(6);
});

test("getOverview omits person_id for Joint", async () => {
  const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({}) });
  vi.stubGlobal("fetch", fetchMock);
  await getOverview({});
  expect(fetchMock.mock.calls[0][0]).toBe("/api/overview");
});
```

- [ ] **Step 2: Run it (fails — no module)**

```bash
npm --prefix web test -- src/lib/api.test.ts
```
Expected: FAIL (cannot find `./api`).

- [ ] **Step 3: Implement `lib/api.ts`**

```ts
const BASE = "/api";

function qs(params: Record<string, string | number | undefined>): string {
  const entries = Object.entries(params).filter(([, v]) => v !== undefined && v !== "");
  if (entries.length === 0) return "";
  const sp = new URLSearchParams();
  for (const [k, v] of entries) sp.set(k, String(v));
  return `?${sp.toString()}`;
}

export async function apiGet<T>(path: string, params: Record<string, string | number | undefined> = {}): Promise<T> {
  const res = await fetch(`${BASE}${path}${qs(params)}`);
  if (!res.ok) throw new Error(`GET ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export async function apiSend<T>(method: "POST" | "PATCH" | "PUT" | "DELETE", path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method,
    headers: body === undefined ? {} : { "Content-Type": "application/json" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${method} ${path} -> ${res.status}`);
  return res.json() as Promise<T>;
}

export type Person = { id: number; name: string };
export type Overview = {
  month: string | null;
  months: string[];
  income: number;
  spend: number;
  net: number;
  savings_rate: number | null;
  complete: boolean;
  by_category: Record<string, number>;
};

export const getPeople = () => apiGet<Person[]>("/people");
export const getOverview = (p: { personId?: number; month?: string }) =>
  apiGet<Overview>("/overview", { person_id: p.personId, month: p.month });
```
Note: `URLSearchParams` orders keys by insertion; `person_id` is added before `month`, matching the test's expected `?person_id=1&month=2026-05`.

- [ ] **Step 4: Run it (passes)**

```bash
npm --prefix web test -- src/lib/api.test.ts
```
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/api.ts web/src/lib/api.test.ts
git commit -m "feat(web): typed API client (people + overview)"
```

---

### Task 3: Persona context (`lib/persona.tsx`)

**Files:**
- Create: `web/src/lib/persona.tsx`, `web/src/lib/persona.test.tsx`

**Interfaces:**
- Produces:
  - `type PersonaKey = "you" | "spouse" | "joint"`
  - `usePersona(): { persona: PersonaKey; setPersona(p: PersonaKey): void; personId?: number; people: Person[]; label: string }`
  - `<PersonaProvider>` — fetches `/api/people`, exposes the active selection, and writes `data-persona` + `--persona` onto `document.documentElement` so the whole tree recolors.
  - Mapping: `you → people[0].id`, `spouse → people[1].id`, `joint → undefined`. `label` = active person's live name, or `"Joint"`.

- [ ] **Step 1: Write the failing test**

Create `web/src/lib/persona.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, test, vi } from "vitest";
import { PersonaProvider, usePersona } from "./persona";

afterEach(() => vi.restoreAllMocks());

function Probe() {
  const { label, personId, setPersona } = usePersona();
  return (
    <div>
      <span data-testid="label">{label}</span>
      <span data-testid="pid">{personId ?? "none"}</span>
      <button onClick={() => setPersona("spouse")}>spouse</button>
      <button onClick={() => setPersona("joint")}>joint</button>
    </div>
  );
}

test("maps personas to person_id and recolors via --persona", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue({
    ok: true, json: async () => [{ id: 7, name: "Ada" }, { id: 9, name: "Mara" }],
  }));
  render(<PersonaProvider><Probe /></PersonaProvider>);

  await waitFor(() => expect(screen.getByTestId("label")).toHaveTextContent("Ada"));
  expect(screen.getByTestId("pid")).toHaveTextContent("7");
  expect(document.documentElement.dataset.persona).toBe("you");

  await userEvent.click(screen.getByText("spouse"));
  expect(screen.getByTestId("pid")).toHaveTextContent("9");
  expect(document.documentElement.dataset.persona).toBe("spouse");

  await userEvent.click(screen.getByText("joint"));
  expect(screen.getByTestId("pid")).toHaveTextContent("none");
  expect(document.documentElement.dataset.persona).toBe("joint");
});
```

- [ ] **Step 2: Run it (fails)**

```bash
npm --prefix web test -- src/lib/persona.test.tsx
```
Expected: FAIL (no module).

- [ ] **Step 3: Implement `lib/persona.tsx`**

```tsx
import { createContext, useContext, useEffect, useMemo, useState } from "react";
import { getPeople, type Person } from "./api";

export type PersonaKey = "you" | "spouse" | "joint";

type PersonaCtx = {
  persona: PersonaKey;
  setPersona: (p: PersonaKey) => void;
  personId?: number;
  people: Person[];
  label: string;
};

const Ctx = createContext<PersonaCtx | null>(null);

export function PersonaProvider({ children }: { children: React.ReactNode }) {
  const [people, setPeople] = useState<Person[]>([]);
  const [persona, setPersona] = useState<PersonaKey>("you");

  useEffect(() => {
    getPeople().then(setPeople).catch(() => setPeople([]));
  }, []);

  useEffect(() => {
    const el = document.documentElement;
    el.dataset.persona = persona;
    el.style.setProperty(
      "--persona",
      persona === "spouse" ? "var(--persona-spouse)" : "var(--persona-you)",
    );
  }, [persona]);

  const personId =
    persona === "you" ? people[0]?.id
    : persona === "spouse" ? people[1]?.id
    : undefined;

  const label =
    persona === "joint" ? "Joint"
    : (persona === "you" ? people[0]?.name : people[1]?.name) ?? (persona === "you" ? "You" : "Spouse");

  const value = useMemo(
    () => ({ persona, setPersona, personId, people, label }),
    [persona, personId, people, label],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function usePersona(): PersonaCtx {
  const v = useContext(Ctx);
  if (!v) throw new Error("usePersona must be used within <PersonaProvider>");
  return v;
}
```

- [ ] **Step 4: Run it (passes)**

```bash
npm --prefix web test -- src/lib/persona.test.tsx
```
Expected: 1 passed (3 assertions across the persona switches).

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/persona.tsx web/src/lib/persona.test.tsx
git commit -m "feat(web): persona context (You/Spouse/Joint) with accent swap"
```

---

### Task 4: Theme context (`lib/theme.tsx`)

**Files:**
- Create: `web/src/lib/theme.tsx`

**Interfaces:**
- Produces: `<ThemeProvider>`, `useTheme(): { theme: "light" | "dark"; toggle(): void }`. Persists to `localStorage["hf-theme"]`; toggles `.dark` on `<html>`.

- [ ] **Step 1: Implement `lib/theme.tsx`**

```tsx
import { createContext, useContext, useEffect, useState } from "react";

type Theme = "light" | "dark";
const Ctx = createContext<{ theme: Theme; toggle: () => void } | null>(null);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState<Theme>(
    () => (localStorage.getItem("hf-theme") as Theme) || "light",
  );
  useEffect(() => {
    document.documentElement.classList.toggle("dark", theme === "dark");
    localStorage.setItem("hf-theme", theme);
  }, [theme]);
  const toggle = () => setTheme((t) => (t === "light" ? "dark" : "light"));
  return <Ctx.Provider value={{ theme, toggle }}>{children}</Ctx.Provider>;
}

export function useTheme() {
  const v = useContext(Ctx);
  if (!v) throw new Error("useTheme must be used within <ThemeProvider>");
  return v;
}
```

- [ ] **Step 2: Build sanity**

```bash
npm --prefix web run build
```
Expected: build OK (no usage yet; wired in Task 6).

- [ ] **Step 3: Commit**

```bash
git add web/src/lib/theme.tsx
git commit -m "feat(web): dark-mode theme context"
```

---

### Task 5: Money formatting helper + PagePlaceholder

**Files:**
- Create: `web/src/components/money.tsx`, `web/src/components/money.test.tsx`, `web/src/components/page-placeholder.tsx`

**Interfaces:**
- Produces:
  - `formatMoney(n: number, opts?: { sign?: boolean }): string` — USD, 2 decimals, thousands separators.
  - `<Money value={number} colored?={boolean} />` — tabular-nums; green (`--pos`) when > 0 and `colored`, red (`--neg`) when < 0 and `colored`.
  - `<PagePlaceholder title={string} />` — used by not-yet-built routes.

- [ ] **Step 1: Write the failing test**

Create `web/src/components/money.test.tsx`:
```tsx
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { Money, formatMoney } from "./money";

test("formatMoney formats USD with separators", () => {
  expect(formatMoney(1234.5)).toBe("$1,234.50");
  expect(formatMoney(-99)).toBe("-$99.00");
});

test("Money colors negatives", () => {
  render(<Money value={-10} colored />);
  const el = screen.getByText("-$10.00");
  expect(el).toHaveStyle({ color: "var(--neg)" });
});
```

- [ ] **Step 2: Run it (fails)**

```bash
npm --prefix web test -- src/components/money.test.tsx
```
Expected: FAIL.

- [ ] **Step 3: Implement `components/money.tsx`**

```tsx
const FMT = new Intl.NumberFormat("en-US", { style: "currency", currency: "USD" });

export function formatMoney(n: number): string {
  return FMT.format(n);
}

export function Money({ value, colored = false }: { value: number; colored?: boolean }) {
  const color = !colored ? undefined : value > 0 ? "var(--pos)" : value < 0 ? "var(--neg)" : undefined;
  return (
    <span style={{ fontVariantNumeric: "tabular-nums", color }}>{formatMoney(value)}</span>
  );
}
```

- [ ] **Step 4: Implement `components/page-placeholder.tsx`**

```tsx
export function PagePlaceholder({ title }: { title: string }) {
  return (
    <div className="frosted-card" style={{ padding: 32 }}>
      <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>{title}</h1>
      <p style={{ color: "var(--fl-muted)", marginTop: 8 }}>Coming soon — built in a later plan.</p>
    </div>
  );
}
```

- [ ] **Step 5: Run it (passes)**

```bash
npm --prefix web test -- src/components/money.test.tsx
```
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add web/src/components/money.tsx web/src/components/money.test.tsx web/src/components/page-placeholder.tsx
git commit -m "feat(web): money formatter + page placeholder"
```

---

### Task 6: Sidebar shell + routing

**Files:**
- Create: `web/src/components/app-sidebar.tsx`, `web/src/routes.tsx`, `web/src/pages/Overview.tsx` (temporary stub, replaced in Task 7)
- Modify: `web/src/App.tsx`, `web/src/main.tsx`

**Interfaces:**
- Consumes: `usePersona`, `useTheme`, `PagePlaceholder`.
- Produces: routes `/` (Overview), `/transactions`, `/budgets`, `/recurring`, `/goals`, `/networth`, `/import`, `/insights`, `/settings`. `AppLayout` renders the sidebar + `<Outlet/>`. The persona switch and theme toggle live in the sidebar.

- [ ] **Step 1: Add the shadcn sidebar (optional but preferred)**

Use the shadcn MCP (`get_add_command_for_items` for `sidebar`) then:
```bash
cd web && npx shadcn@latest add sidebar ; cd ..
```
If you prefer to avoid the sidebar block's surface area at this stage, skip this and use the plain markup in Step 2 (it does not import the shadcn sidebar). Decide by eye; the rest of the plan does not depend on the shadcn sidebar primitive.

- [ ] **Step 2: Implement `components/app-sidebar.tsx`**

```tsx
import { NavLink } from "react-router-dom";
import { usePersona, type PersonaKey } from "@/lib/persona";
import { useTheme } from "@/lib/theme";

const NAV: { to: string; label: string }[] = [
  { to: "/", label: "Overview" },
  { to: "/transactions", label: "Transactions" },
  { to: "/budgets", label: "Budgets" },
  { to: "/recurring", label: "Recurring" },
  { to: "/goals", label: "Goals" },
  { to: "/networth", label: "Net Worth" },
  { to: "/import", label: "＋ Import" },
  { to: "/insights", label: "AI Insights" },
  { to: "/settings", label: "Settings" },
];

const PERSONAS: { key: PersonaKey; text: string }[] = [
  { key: "you", text: "You" },
  { key: "spouse", text: "Spouse" },
  { key: "joint", text: "Joint" },
];

export function AppSidebar() {
  const { persona, setPersona, people } = usePersona();
  const { theme, toggle } = useTheme();
  const text = (k: PersonaKey) =>
    k === "you" ? people[0]?.name ?? "You" : k === "spouse" ? people[1]?.name ?? "Spouse" : "Joint";

  return (
    <aside data-persona-seam={persona} style={{ width: 232, padding: 16, borderRight: "1px solid var(--fl-line)" }}>
      <div role="tablist" aria-label="Persona" style={{ display: "flex", gap: 6, marginBottom: 20 }}>
        {PERSONAS.map((p) => (
          <button
            key={p.key}
            role="tab"
            aria-selected={persona === p.key}
            onClick={() => setPersona(p.key)}
            style={{
              flex: 1, padding: "6px 8px", borderRadius: 999, fontSize: 13,
              border: "1px solid var(--fl-line)",
              background: persona === p.key ? "var(--persona)" : "transparent",
              color: persona === p.key ? "#fff" : "var(--fl-ink)",
            }}
          >
            {text(p.key)}
          </button>
        ))}
      </div>

      <nav style={{ display: "flex", flexDirection: "column", gap: 2 }}>
        {NAV.map((n) => (
          <NavLink
            key={n.to}
            to={n.to}
            end={n.to === "/"}
            style={({ isActive }) => ({
              padding: "8px 12px", borderRadius: 10, textDecoration: "none",
              color: isActive ? "var(--persona)" : "var(--fl-ink)",
              background: isActive ? "color-mix(in srgb, var(--persona) 10%, transparent)" : "transparent",
              fontWeight: isActive ? 700 : 500,
            })}
          >
            {n.label}
          </NavLink>
        ))}
      </nav>

      <button onClick={toggle} style={{ marginTop: 24, fontSize: 13, color: "var(--fl-muted)", background: "none", border: "none", cursor: "pointer" }}>
        {theme === "dark" ? "☀ Light" : "☾ Dark"}
      </button>
    </aside>
  );
}
```

- [ ] **Step 3: Temporary Overview stub** (replaced in Task 7)

Create `web/src/pages/Overview.tsx`:
```tsx
export default function Overview() {
  return <div>Overview</div>;
}
```

- [ ] **Step 4: Route table `routes.tsx`**

```tsx
import { createBrowserRouter, Outlet } from "react-router-dom";
import { AppSidebar } from "@/components/app-sidebar";
import { PagePlaceholder } from "@/components/page-placeholder";
import Overview from "@/pages/Overview";

function AppLayout() {
  return (
    <div className="frosted-canvas" style={{ display: "flex", minHeight: "100vh" }}>
      <AppSidebar />
      <main style={{ flex: 1, padding: 24 }}><Outlet /></main>
    </div>
  );
}

export const router = createBrowserRouter([
  {
    path: "/",
    element: <AppLayout />,
    children: [
      { index: true, element: <Overview /> },
      { path: "transactions", element: <PagePlaceholder title="Transactions" /> },
      { path: "budgets", element: <PagePlaceholder title="Budgets" /> },
      { path: "recurring", element: <PagePlaceholder title="Recurring" /> },
      { path: "goals", element: <PagePlaceholder title="Goals" /> },
      { path: "networth", element: <PagePlaceholder title="Net Worth" /> },
      { path: "import", element: <PagePlaceholder title="Import" /> },
      { path: "insights", element: <PagePlaceholder title="AI Insights" /> },
      { path: "settings", element: <PagePlaceholder title="Settings" /> },
    ],
  },
]);
```

- [ ] **Step 5: Wire providers + router in `App.tsx`**

Replace `web/src/App.tsx`:
```tsx
import { RouterProvider } from "react-router-dom";
import { PersonaProvider } from "@/lib/persona";
import { ThemeProvider } from "@/lib/theme";
import { router } from "@/routes";

export default function App() {
  return (
    <ThemeProvider>
      <PersonaProvider>
        <RouterProvider router={router} />
      </PersonaProvider>
    </ThemeProvider>
  );
}
```
Confirm `web/src/main.tsx` renders `<App />` inside `<StrictMode>` (the Vite template already does; keep the `import "./index.css"` and the Plan 2 font import).

- [ ] **Step 6: Build + run, click through nav**

```bash
npm --prefix web run build
```
Expected: build OK. (Manual dev check optional — `npm --prefix web run dev`, click each nav item, toggle theme, switch persona; placeholders show for unbuilt pages.)

- [ ] **Step 7: Commit**

```bash
git add web/src
git commit -m "feat(web): sidebar shell, persona switch, theme toggle, routing"
```

---

### Task 7: Overview page wired to `/api/overview`

**Files:**
- Modify: `web/src/pages/Overview.tsx` (replace stub)
- Create: `web/src/pages/Overview.test.tsx`

**Interfaces:**
- Consumes: `usePersona().personId/label`, `getOverview`, `<Money/>`, `formatMoney`.
- Produces: a dashboard showing the active month's headline KPIs (income / spend / net / savings rate), a month stepper over `months`, and a category breakdown from `by_category`.

Scope note: the existing `/api/overview` returns one month's totals + the month list + that month's `by_category`. This page renders exactly that. The spec §5 signature charts (hatched cash-flow time series, who-spent-what dot-matrix) require a time-series endpoint and are **deferred** — flagged as follow-up in Plan 10's parity list, not built here.

- [ ] **Step 1: Write the failing test**

Create `web/src/pages/Overview.test.tsx`:
```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, test, vi } from "vitest";

vi.mock("@/lib/persona", () => ({
  usePersona: () => ({ persona: "you", personId: 1, label: "Ada", people: [], setPersona: () => {} }),
}));
vi.mock("@/lib/api", () => ({
  getOverview: vi.fn().mockResolvedValue({
    month: "2026-05", months: ["2026-04", "2026-05"],
    income: 5000, spend: 2400, net: 2600, savings_rate: 0.52, complete: true,
    by_category: { Housing: 2000, Groceries: 300, "Eating out": 100 },
  }),
}));

import Overview from "./Overview";

afterEach(() => vi.restoreAllMocks());

test("renders headline numbers and category breakdown", async () => {
  render(<Overview />);
  await waitFor(() => expect(screen.getByTestId("net")).toHaveTextContent("$2,600.00"));
  expect(screen.getByTestId("income")).toHaveTextContent("$5,000.00");
  expect(screen.getByTestId("spend")).toHaveTextContent("$2,400.00");
  expect(screen.getByText("52%")).toBeInTheDocument();
  expect(screen.getByText("Housing")).toBeInTheDocument();
});
```

- [ ] **Step 2: Run it (fails — stub has no testids)**

```bash
npm --prefix web test -- src/pages/Overview.test.tsx
```
Expected: FAIL.

- [ ] **Step 3: Implement `pages/Overview.tsx`**

```tsx
import { useEffect, useMemo, useState } from "react";
import { getOverview, type Overview as OverviewData } from "@/lib/api";
import { usePersona } from "@/lib/persona";
import { Money, formatMoney } from "@/components/money";

export default function Overview() {
  const { personId, label } = usePersona();
  const [data, setData] = useState<OverviewData | null>(null);
  const [month, setMonth] = useState<string | undefined>(undefined);

  useEffect(() => {
    let alive = true;
    getOverview({ personId, month }).then((d) => alive && setData(d)).catch(() => alive && setData(null));
    return () => { alive = false; };
  }, [personId, month]);

  const cats = useMemo(
    () => Object.entries(data?.by_category ?? {}).sort((a, b) => b[1] - a[1]),
    [data],
  );
  const maxCat = cats.length ? cats[0][1] : 1;

  if (!data) return <div style={{ color: "var(--fl-muted)" }}>Loading…</div>;

  const rate = data.savings_rate;
  const idx = data.months.indexOf(data.month ?? "");
  const step = (delta: number) => {
    const next = data.months[idx + delta];
    if (next) setMonth(next);
  };

  return (
    <div style={{ display: "grid", gap: 16 }}>
      <header style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <h1 style={{ fontWeight: 800, letterSpacing: "-0.03em", margin: 0 }}>Overview · {label}</h1>
        <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 8 }}>
          <button onClick={() => step(-1)} disabled={idx <= 0} aria-label="Previous month">‹</button>
          <span style={{ fontWeight: 700 }}>{data.month ?? "—"}</span>
          <button onClick={() => step(1)} disabled={idx < 0 || idx >= data.months.length - 1} aria-label="Next month">›</button>
        </div>
      </header>

      <section className="frosted-card" style={{ padding: 24, display: "flex", gap: 32 }}>
        <Kpi label="Income" testId="income"><Money value={data.income} /></Kpi>
        <Kpi label="Spending" testId="spend"><Money value={data.spend} /></Kpi>
        <Kpi label="Net" testId="net" big><Money value={data.net} colored /></Kpi>
        <Kpi label="Savings rate" testId="savings">
          {rate == null ? "—" : `${Math.round(rate * 100)}%`}
        </Kpi>
      </section>

      <section className="frosted-card" style={{ padding: 24 }}>
        <h2 style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--fl-muted)" }}>By category</h2>
        <div style={{ display: "grid", gap: 8, marginTop: 12 }}>
          {cats.map(([name, amount]) => (
            <div key={name} style={{ display: "grid", gridTemplateColumns: "140px 1fr 90px", alignItems: "center", gap: 12 }}>
              <span>{name}</span>
              <div style={{ height: 10, borderRadius: 999, background: "var(--fl-line)" }}>
                <div style={{ height: 10, borderRadius: 999, width: `${(amount / maxCat) * 100}%`, background: "var(--persona)" }} />
              </div>
              <span style={{ textAlign: "right", fontVariantNumeric: "tabular-nums" }}>{formatMoney(amount)}</span>
            </div>
          ))}
        </div>
      </section>
    </div>
  );
}

function Kpi({ label, testId, big = false, children }: { label: string; testId: string; big?: boolean; children: React.ReactNode }) {
  return (
    <div style={{ display: "grid", gap: 4 }}>
      <span style={{ fontSize: 12, textTransform: "uppercase", letterSpacing: "0.08em", color: "var(--fl-muted)" }}>{label}</span>
      <span
        data-testid={testId}
        style={big ? { fontSize: 32, fontWeight: 800, letterSpacing: "-0.03em" } : { fontSize: 18, fontWeight: 700 }}
      >
        {children}
      </span>
    </div>
  );
}
```
Note: each `Kpi` puts an explicit, **unique** `data-testid` (`income`, `spend`, `net`, `savings`) on the *value* span, matching the test's `getByTestId` calls exactly. (Do NOT derive the testid from the label — "Spending" would yield `spending`, not the `spend` the test queries; and a wrapper-plus-value pair would make `getByTestId("net")` ambiguous.)

- [ ] **Step 4: Run it (passes)**

```bash
npm --prefix web test -- src/pages/Overview.test.tsx
```
Expected: 1 passed.

- [ ] **Step 5: Full web test suite + build**

```bash
npm --prefix web test
npm --prefix web run build
```
Expected: all suites pass; build OK.

- [ ] **Step 6: End-to-end smoke against the real API (optional, recommended)**

```bash
VPY="C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe"
"$VPY" -m uvicorn backend.main:app --port 8000 --log-level warning &
APID=$!
npm --prefix web run dev &
VPID=$!
# Open http://localhost:5173 in a browser; confirm Overview loads, persona switch refetches,
# theme toggles, nav routes render placeholders. Then:
kill $APID $VPID
```

- [ ] **Step 7: Commit**

```bash
git add web/src/pages/Overview.tsx web/src/pages/Overview.test.tsx
git commit -m "feat(web): Overview dashboard wired to /api/overview"
```

---

## Self-Review

**1. Spec coverage** (spec §4 IA/persona, §5 Overview, §3/§13 theme):
- Left sidebar + persona switch pinned top + full nav order → Task 6. ✓
- Persona = You/Spouse/Joint mapped to `person_id`, recolors accent → Task 3. ✓
- Dark-mode toggle in chrome, `.dark` class → Task 4 + Task 6. ✓
- Overview headline KPIs + month stepper + category breakdown from live `/api/overview` → Task 7. ✓
- **Deferred (flagged):** §5 hatched cash-flow time series + who-spent-what dot-matrix need a time-series endpoint — noted in Task 7 and Plan 10 parity list. The other nav pages are stubs filled by Plans 4–9.

**2. Placeholder scan:** every component, test, and route has complete code. `PagePlaceholder` is real, shipped UI for not-yet-built routes (its plan-step code is fully specified) — not a plan placeholder.

**3. Type/interface consistency:** `getOverview({ personId, month })` and the `Overview` type (Task 2) are consumed identically in Task 7; `usePersona()` shape (Task 3) matches its consumers in Tasks 6–7; `--persona` is written by Task 3 and read by Tasks 6–7; route paths in Task 6 match the nav `to` values. The `person_id`/`month` query-param names match the backend `overview(person_id, month)` signature verified in `backend/api/overview.py`.

**Out of scope (later plans):** Transactions table (Plan 4), Budgets/Goals (Plan 5), Net Worth/Recurring (Plan 6), Settings (Plan 7), Import (Plan 8), AI Insights (Plan 9), cutover (Plan 10).
