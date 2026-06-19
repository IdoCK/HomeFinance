# HomeFinance UI Rewrite — Design Spec

**Date:** 2026-06-18
**Status:** Draft for review
**Branch context:** created during `feature/recurring-detection`; the rewrite is a new milestone, not part of that branch.

## 1. Summary

Replace the Streamlit UI with a modern React + shadcn/ui single-page app, served by a
thin FastAPI layer that **reuses the existing Python engine (`modules/`) and SQLite
database unchanged**. The visual identity is **"Frosted Ledger"** — the soft, airy,
monochrome-plus-vivid aesthetic of the zentra reference dashboard, fused with the app's
one truly distinctive trait: it is a **two-person household ledger** (You / Spouse /
Joint), expressed as a "two inks" color system (You = blue, Spouse = pink, Joint = both).

This is a **ground-up rethink** of the UX (information architecture, navigation, theming,
dashboards, data flow, import flow), but it preserves every current capability and the
local-first privacy guarantee.

### Goals
- Modern, distinctive, non-templated UI grounded in the zentra reference and the
  two-person brief.
- Left-sidebar navigation (locked decision).
- Reuse the Python engine: pandas analytics, the local Ollama parsing/categorization
  agent, Anthropic insights, SQLite — all stay in Python behind FastAPI.
- One-command local run, no Node runtime required in production.
- Preserve the privacy model: raw data never leaves the machine; only anonymized
  aggregates are sent for AI insights, with a preview before sending.

### Non-goals (YAGNI)
- No authentication / multi-tenant / cloud hosting. It stays a local, single-machine,
  two-person tool.
- No real-time collaboration, no mobile-native app (responsive web is enough).
- No rewrite of the Python engine logic. We wrap it, we don't reimplement it.
- No new persistence layer; keep `data/finance.db` and the existing schema.

## 2. Architecture

```
Browser  ──  React SPA (Vite + shadcn/ui + Tailwind)
   │  fetch JSON  (dev: Vite proxy → :8000)
   ▼
FastAPI  (new, thin: app/api/*.py)
   │  direct function calls
   ▼
modules/  (REUSED AS-IS: database, analytics, agent_parser, ai_insights, formats, keywords)
   │
   ▼
data/finance.db  (SQLite, unchanged schema)
```

- **Dev:** `vite dev` (5173) + `uvicorn` (8000); Vite proxies `/api/*` to FastAPI.
- **Prod/local:** `vite build` emits static assets; FastAPI serves the built SPA and the
  API from one `uvicorn` process on one port. Single command to run.
- The FastAPI layer is intentionally thin — request validation (Pydantic) and a direct
  call into a `modules/` function. No business logic is added in the API layer; if logic
  is missing it goes into `modules/`, keeping the engine the single source of truth and
  keeping it unit-testable without HTTP.

### Project structure (added)
```
backend/                  # FastAPI backend (new)
  main.py                 # app factory, static-file serving, CORS for dev
  api/
    people.py  transactions.py  imports.py  categories.py
    budgets.py  goals.py  networth.py  analytics.py  insights.py  agent.py
  schemas.py              # Pydantic request/response models
web/                      # React SPA (new)
  index.html  vite.config.ts  components.json  tailwind config
  src/
    main.tsx  App.tsx  router
    lib/api.ts            # typed fetch client
    lib/persona.tsx       # persona context (You/Spouse/Joint) → active ink
    components/ui/*        # shadcn components (generated)
    components/charts/*    # cash-flow (hatched), dot-matrix, savings bars
    components/app-sidebar.tsx
    pages/Overview Transactions Budgets Recurring Goals NetWorth Import Insights Settings
modules/                  # UNCHANGED engine
data/finance.db           # UNCHANGED
app.py                    # legacy Streamlit app — retired after parity (see §11)
```

## 3. Visual Identity — "Frosted Ledger"

### Color tokens (light)
| Token | Hex | Use |
|---|---|---|
| canvas | `#E5E6EA` | app background behind the frame |
| frame | `#F6F7F9` | the rounded app surface |
| card | `#FFFFFF` | cards |
| line | `#ECEDF0` | hairline borders |
| ink | `#16181D` | primary text & big numbers |
| muted | `#8A8F98` | labels |
| **You** | `#3B82F6` (deep `#2563EB`) | persona accent — You |
| **Spouse** | `#EC4899` | persona accent — Spouse |
| **Joint** | blue→pink gradient | persona accent — Joint |
| income/positive | `#22C55E` | gains, income, positive deltas |
| over/negative | `#EF4444` | over-budget / negative (used sparingly; distinct from Spouse pink) |
| accent-3 | `#A855F7` | "saved" / tertiary series |
| showpiece gradient | `#FDBA74 → #F472B6 → #A855F7 → #3B82F6` | the one glassy hero (AI Insights) |

Dark mode ("after-dark"): deep neutral canvas, brightened inks; defined as the same
tokens under `.dark`. Theme toggle in the top bar. shadcn neutral base = **slate**;
brand colors layered as CSS variables (`--primary`, `--chart-1..5`, `--persona-*`).

### Typography
- **Plus Jakarta Sans** for everything — geometric grotesque matching the reference's
  big bold numerals. Weights 400–800.
- Big numbers: 800 weight, tight tracking (`-0.03em`). Tabular numerals (`font-variant-
  numeric: tabular-nums`) in tables and money columns so figures align like a ledger.
- (The earlier "monospace ledger figures" idea is dropped in favor of the reference's
  bold sans.)

### Signature elements (where the boldness is spent)
1. **Two-ink persona system** — the persona switch recolors the active accent across the
   whole view. The sidebar carries a "ledger seam": solid blue in You, solid pink in
   Spouse, blue→pink gradient in Joint.
2. **"Who spent what" dot-matrix** — a blue/pink dot grid splitting Joint spend between
   the two people. The one module no single-user finance app has. (Fallback if it reads
   poorly: a single blue/pink split bar — decided at build by eye.)
3. **Glassy gradient showpiece** — reserved for **AI Insights** only; everything else
   stays quiet (soft cards, neutral chrome).

Everything else is disciplined: soft rounded cards (radius ~18px), generous whitespace,
pill controls, hatched/gradient charts, tiny uppercase labels.

## 4. Information Architecture

Left sidebar, persona switch pinned at top. Today's 7 Streamlit tabs become:

**Primary nav (Money):**
- **Overview** — the dashboard (see §5).
- **Transactions** — the full ledger: TanStack data table, inline category edit, include
  toggle, filter bar. (Merges old Dashboard table + Analysis filtering.)
- **Budgets** — surfaces the latent budgets schema as a first-class page.
- **Recurring** — subscription/recurring detection (the in-flight feature) as a page.
- **Goals** — savings goals.
- **Net Worth** — accounts + snapshots over time.

**Utility (below divider):**
- **＋ Import** — accented; the import wizard (see §6).
- **AI Insights** — anonymized-aggregate preview → Anthropic.
- **Settings** — absorbs Categories, vendor groups, rename people, privacy info.

Persona model: a React context (`lib/persona.tsx`) holds `You | Spouse | Joint`. Every
data fetch passes the persona; `Joint` = all people merged (matches today's
`person_id=None`/`"all"` semantics in `database.py`).

## 5. Overview page (the dashboard)

Mirrors the validated mockup (`web` equivalent of `style-zentra.html`):
- **Top bar:** "Overview · {persona}", month stepper pill, compare-to pill, granularity
  pill, theme toggle.
- **Row 1:** **Cash flow** card (hatched + gradient area chart, in/out/net KPIs, inline
  AI explore input) spanning 2/3; **This month** card (big net number + green delta +
  Income/Spending/Saved rows with mini bars) 1/3.
- **Row 2:** **Savings rate** (pink bar history) · **Who spent what** (dot-matrix, Joint
  signature; in single-persona view this becomes that person's category split) · **AI
  Insights** glassy showpiece (latest insight teaser → links to Insights page).
- Recurring "new subscription detected" surfaces as an alert chip when applicable.

## 6. Import flow (redesigned)

Today: a dense single tab. New: a guided **wizard** (shadcn `tabs`/stepper + `dialog`),
preserving the local-agent magic:
1. **Drop file** — drag/drop or pick (Amazon / card / bank / auto). `dialog`/`drawer`,
   Ollama-ready 🟢/🔴 indicator.
2. **Auto-detect** — the local agent parses columns/format; show detected mapping with a
   confidence note; allow "learn a new format" when unmatched.
3. **Review & categorize** — preview table, auto-categorize via local agent, inline fix,
   include/exclude rows; optional "statement ending balance → refresh a Net Worth
   account."
4. **Confirm** — counts, then commit (`add_transactions` + `record_import`).
Progress is streamed from the backend (agent steps) via a simple polling or SSE endpoint.

## 7. Data flow & API surface

Thin REST endpoints, each delegating to an existing `modules/` function. Representative
map (not exhaustive):

| Method & path | Backend call |
|---|---|
| `GET /api/people` / `PATCH /api/people/{id}` | `db.list_people` / `db.rename_person` |
| `GET /api/transactions?persona=` | `db.get_transactions` |
| `PATCH /api/transactions/{id}` | `db.set_transaction_category` / `set_transaction_included` |
| `GET /api/overview?persona=&month=` | `analytics` KPIs/trends + cash-flow aggregates |
| `GET /api/analytics/by-category?…` | `analytics.filter_transactions` + grouping |
| `GET /api/recurring?persona=` | recurring detection in `analytics` |
| `GET/POST/DELETE /api/categories` `…/vendors` | `db.get_categories`/`upsert_*`/`delete_*` |
| `GET/PUT/DELETE /api/budgets` | `db.get_budgets` / `set_budget` / `delete_budget` |
| `GET/POST/PATCH/DELETE /api/goals` | `db.get_goals` / `add_goal` / `update_goal_saved` / `delete_goal` |
| `GET/POST/PATCH/DELETE /api/accounts` + snapshots | `db.list_accounts` / `add_account` / `update_account_balance` / `account_snapshots` |
| `POST /api/import/parse` (multipart) | `agent_parser` (Ollama) |
| `POST /api/import/categorize` | `keywords.classify_descriptions` + `agent_parser` |
| `POST /api/import/commit` | `db.add_transactions` + `db.record_import` |
| `GET /api/insights/preview` / `POST /api/insights/generate` | `ai_insights` (Anthropic) |
| `GET /api/agent/status` | Ollama health check |

Privacy stays intact: `/api/insights/preview` returns the exact anonymized aggregate
payload for the UI to display before `/generate` is allowed to call out. Ollama and
Anthropic calls remain entirely in the Python backend; the browser never holds keys.

## 8. shadcn component map

Base: `npx shadcn@latest init` in `web/` (slate base), then add. Real registry items:

- **Shell/nav:** `@shadcn/sidebar` (+ block `@shadcn/sidebar-01` as starting point),
  `@shadcn/breadcrumb`, `@shadcn/separator`, `@shadcn/avatar`, `@shadcn/dropdown-menu`.
- **Layout/data:** `@shadcn/card`, `@shadcn/tabs`, `@shadcn/table` (compose TanStack per
  `data-table-demo`), `@shadcn/pagination`, `@shadcn/scroll-area`, `@shadcn/badge`,
  `@shadcn/progress`, `@shadcn/skeleton`, `@shadcn/empty`.
- **Charts:** `@shadcn/chart` (Recharts wrapper) — reference blocks `chart-bar-interactive`,
  `chart-area-*`; cash-flow hatch + dot-matrix are custom on top of the chart primitives.
- **Forms/controls:** `@shadcn/button`, `@shadcn/button-group`, `@shadcn/input`,
  `@shadcn/input-group`, `@shadcn/select`, `@shadcn/combobox`, `@shadcn/switch`,
  `@shadcn/checkbox`, `@shadcn/label`, `@shadcn/form`, `@shadcn/slider` (month range),
  `@shadcn/popover`, `@shadcn/calendar` (goal target date).
- **Overlays/feedback:** `@shadcn/dialog`, `@shadcn/drawer`, `@shadcn/sheet`,
  `@shadcn/alert`, `@shadcn/alert-dialog`, `@shadcn/tooltip`, `@shadcn/sonner` (toasts),
  `@shadcn/spinner`.
- The shadcn MCP (`search_items_in_registries`, `get_item_examples_from_registries`,
  `get_add_command_for_items`) is used during implementation to pull exact add commands
  and demo code per component.

## 9. Two-person / persona behavior (detail)
- Persona is a global UI state; switching it refetches the active page scoped to that
  persona and recolors the accent (`--persona` CSS var swap).
- `Joint` unlocks comparative modules (Who-spent-what, side-by-side goal progress,
  per-person net-worth contribution). Single-persona views hide comparison, show that
  person's own breakdowns.
- People are renameable (Settings) — "You"/"Spouse" are seeded defaults, as today.

## 10. Testing
- **Engine:** existing `tests/` (analytics, keywords, networth, recurring, advanced)
  keep passing — the rewrite must not touch their behavior.
- **API:** FastAPI `TestClient` tests per router (happy path + validation), using a
  temp SQLite db fixture.
- **Frontend:** component tests (Vitest + Testing Library) for persona switching, the
  data table editing, and the import wizard state machine; a smoke e2e (Playwright) for
  the import → overview flow is optional/stretch.
- TDD per the project's workflow: write the failing API/engine test before the endpoint.

## 11. Migration / phasing
The implementation plan (writing-plans, next step) will sequence these waves:
1. **Backend scaffold** — FastAPI app, static serving, persona param, people +
   transactions endpoints, API tests. Streamlit still runs in parallel.
2. **Frontend scaffold** — Vite + shadcn init, design tokens, app shell (sidebar +
   persona context + theme), Overview wired to live data.
3. **Page-by-page** — Transactions, Budgets, Recurring, Goals, Net Worth, Settings,
   each with its endpoints.
4. **Import wizard** — the multi-step flow + agent endpoints + progress streaming.
5. **AI Insights** — preview/generate + the showpiece card.
6. **Cutover** — verify parity against the old app, update README run instructions,
   retire `app.py` (kept in git history). `data/finance.db` is reused throughout, so no
   data migration is needed.

## 12. Decisions locked in this brainstorm
- React **Vite SPA + FastAPI** (not Next.js); FastAPI serves the built SPA.
- **Ground-up** UX rethink; engine + DB reused unchanged.
- **Left sidebar** navigation.
- **"Frosted Ledger"** identity from the zentra reference; **You=blue / Spouse=pink /
  Joint=both**; Plus Jakarta Sans; glassy gradient reserved for AI Insights.
- IA: Overview · Transactions · Budgets · Recurring · Goals · Net Worth · Import ·
  AI Insights · Settings.

## 13. Open items (sensible defaults chosen; revisit if needed)
- Who-spent-what stays a dot-matrix; swap to split bar only if it reads poorly at build.
- Import progress via SSE if simple, else short polling.
- Dark mode delivered with the shell (token set defined up front), not deferred.
