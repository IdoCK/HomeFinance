# UI Rewrite — Plan 2: Frontend Scaffold Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a themed, buildable React (Vite + TypeScript) single-page app under `web/`, wired to shadcn/ui with the "Frosted Ledger" design tokens, and served single-port by the existing FastAPI app — with the backend package renamed `app/` → `backend/` to remove the `app.py` collision.

**Architecture:** A Vite React-TS SPA in `web/` proxies `/api/*` to FastAPI (`:8000`) in dev; `vite build` emits `web/dist`, which FastAPI serves at `/` in prod (single port). shadcn/ui (slate base) provides components; brand identity lives in CSS variables. This wave produces the scaffold and design system only — the app shell (sidebar + persona context + theme toggle), routing, and the Overview page wired to live data are **Plan 3**.

**Tech Stack:** Vite, React 18, TypeScript, Tailwind CSS v4 (`@tailwindcss/vite`), shadcn/ui, FastAPI (existing). Node v24.16.0 / npm 11.13.0 are **already installed** (verified in this worktree); Task 3 only verifies the toolchain — no install needed.

## Working Context
- This runs in the worktree at `.claude/worktrees/ui-rewrite` on branch `feature/ui-rewrite`. The worktree has **no local `venv/`** — use the main repo's interpreter by absolute path for all Python/pytest:
  `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe`
  (verified present; it has `httpx`/`fastapi` so `TestClient` works. The system `py`/`python3` does **not** — always use this venv path.)
- **Node v24 / npm 11 are present** (verified: `node -v` → v24.16.0, `npm -v` → 11.13.0). Tasks 1–2 are pure Python and run first; Tasks 4–5 need Node and run after Task 3's quick verification.
- The shadcn MCP is configured in `.mcp.json` (`npx shadcn@latest mcp`) and is usable (Node is present). Use it (`search_items_in_registries`, `get_item_examples_from_registries`, `get_add_command_for_items`) to get exact add commands / component code rather than guessing.
- A prior wave already added a `GET /` → `/docs` redirect in `app/main.py` for the **dist-absent** case (so the bare URL isn't a 404 in dev). When `web/dist` exists the `StaticFiles` mount serves `/` instead; the redirect only fires when there is no built SPA. Both Task 2's test and the existing `tests/api/test_spa_serving.py` account for this.

## Global Constraints
- Local-only: no auth, no cloud, no analytics, no network calls beyond the localhost dev proxy. (spec §1)
- Reuse the engine unchanged: do NOT modify `modules/*.py`. (spec §1, §2)
- No Node runtime required **in production** — Node is build-time only; FastAPI serves the pre-built `web/dist`. (spec §1)
- Single-port production: FastAPI serves `web/dist` when present, and must not fail when absent. (spec §2)
- Design identity "Frosted Ledger" (spec §3): base = shadcn **slate**; persona accents **You `#3B82F6`** (deep `#2563EB`), **Spouse `#EC4899`**, **Joint = blue→pink**; income/positive `#22C55E`, over/negative `#EF4444`; tertiary/"saved" `#A855F7`; canvas `#E5E6EA`, frame `#F6F7F9`, card `#FFFFFF`, line `#ECEDF0`, ink `#16181D`, muted `#8A8F98`; display/body font **Plus Jakarta Sans** (weights 400–800), tabular numerals for money. Soft rounded cards (~18px), big bold numbers, pill controls.
- Dark mode token set is defined **up front** under `.dark` (spec §13, locked) even though the toggle that switches it lands in Plan 3.
- Do not commit `node_modules/` or `web/dist/` (gitignore them).
- Keep the legacy `app.py` (Streamlit) working — it stays untouched, but no longer collides with a package named `app`.

---

### Task 1: Rename backend package `app/` → `backend/`

**Why:** the FastAPI package `app/` collides with the Streamlit script `app.py`. It currently resolves via Python's package-over-module precedence, but that is fragile (a stale/empty `app/` checkout silently falls through to `app.py`, dragging Streamlit into the API process). Renaming removes the ambiguity before the frontend's run/serve path is built on top of it.

**Files:**
- Rename: `app/` → `backend/` (contents: `backend/__init__.py`, `backend/main.py`, `backend/schemas.py`, `backend/api/{overview,people,transactions}.py`)
- Modify: `run_api.py`, `tests/api/conftest.py`
- Modify (doc): `docs/superpowers/specs/2026-06-18-finance-ui-rewrite-design.md` (§2 structure note `app/` → `backend/`)

**Interfaces:**
- Produces: uvicorn target string `backend.main:app`; test import `from backend import main`; routers import `from backend.api import ...`; schemas import `from backend.schemas import ...`. `backend.main` continues to expose `create_app()`, module-level `app`, and `DIST_DIR`.

- [ ] **Step 1: Move the package**

```bash
git mv app backend
```

- [ ] **Step 2: Find every `app`-package reference**

```bash
grep -rn -E "\bfrom app\.|\bimport app\.|app\.main:app|from app import" backend run_api.py tests/api
```
Expected hits (exact current lines):
- `backend/main.py`: `from app.api import overview, people, transactions`
- `backend/main.py`: a comment referencing `"app.main:app"` and "importing app.main"
- `backend/api/people.py`: `from app.schemas import PersonUpdate`
- `backend/api/transactions.py`: `from app.schemas import TransactionUpdate`
- `run_api.py`: `uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)`
- `tests/api/conftest.py`: `from app import main`

- [ ] **Step 3: Apply the edits**

- `backend/main.py`: `from app.api import overview, people, transactions` → `from backend.api import overview, people, transactions`. In the module-level comment, change `"app.main:app"` → `"backend.main:app"` and "importing app.main" → "importing backend.main" (prose only; keep the meaning).
- `backend/api/people.py`: `from app.schemas import PersonUpdate` → `from backend.schemas import PersonUpdate`.
- `backend/api/transactions.py`: `from app.schemas import TransactionUpdate` → `from backend.schemas import TransactionUpdate`.
- `run_api.py`: `uvicorn.run("app.main:app", ...)` → `uvicorn.run("backend.main:app", ...)`.
- `tests/api/conftest.py`: `from app import main` → `from backend import main`. Leave the `import importlib` / `importlib.reload(main)` / `TestClient(main.create_app())` lines exactly as they are.

Verify none remain:
```bash
grep -rn -E "\bfrom app\.|\bimport app\.|app\.main:app|from app import" backend run_api.py tests/api && echo "STILL PRESENT — fix" || echo "clean"
```
Expected: `clean`.

- [ ] **Step 4: Run the API test suite**

```bash
C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api -q
```
Expected: `13 passed` (a single benign httpx deprecation warning is OK). An `ImportError` or `ModuleNotFoundError` mentioning `app` means a reference was missed in Step 3.

- [ ] **Step 5: Verify import resolution + no Streamlit leakage**

```bash
VPY="C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe"
"$VPY" -c "import backend.main as m; print('OK', type(m.app).__name__, m.DIST_DIR.name)"
"$VPY" -m uvicorn backend.main:app --port 8031 --log-level warning > /tmp/uvi2.log 2>&1 &
PID=$!; curl -s --retry 15 --retry-connrefused --retry-delay 1 http://127.0.0.1:8031/api/health; echo; kill $PID
grep -ic "streamlit\|ScriptRunContext" /tmp/uvi2.log
```
Expected: `OK FastAPI dist`, then `{"status":"ok"}`, then `0` (no Streamlit noise).

- [ ] **Step 6: Update the spec's structure note**

In `docs/superpowers/specs/2026-06-18-finance-ui-rewrite-design.md` §2, change the project-structure line `app/                      # FastAPI backend (new)` to `backend/                  # FastAPI backend (new)`. One line; leave the rest (including the `app.py  # legacy Streamlit app` line) untouched.

- [ ] **Step 7: Commit**

```bash
git add -A
git commit -m "refactor(api): rename app/ -> backend/ to remove app.py collision"
```

---

### Task 2: Verify single-port SPA serving (FastAPI → `web/dist`)

**Why now:** this is pure Python (no Node) and locks the contract the frontend build targets. The existing `tests/api/test_spa_serving.py` already covers the **dist-absent** path (API still works, unknown routes 404). This task adds the missing **dist-present** path: a built `index.html` is served at `/`.

**Files:**
- Create: `tests/api/test_spa_index.py`
- (Expected: **no** change to `backend/main.py`. It already mounts `StaticFiles(web/dist, html=True)` at `/` when `DIST_DIR.is_dir()`. Confirm `DIST_DIR` resolves to `<repo>/web/dist`.)

**Interfaces:**
- Consumes: `backend.main.create_app`, `backend.main.DIST_DIR`, `modules.database.DB_PATH`/`init_db`.
- Produces: with a built `web/dist`, `GET /` returns `index.html` (200); `/api/*` still works.

- [ ] **Step 1: Confirm `DIST_DIR` target**

```bash
C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -c "import backend.main as m; print(m.DIST_DIR)"
```
Expected: a path ending `...\ui-rewrite\web\dist` (i.e. `<repo>/web/dist`). It is computed as `Path(__file__).resolve().parent.parent / "web" / "dist"` — from `backend/main.py`, `parent.parent` is the repo root, so this is correct after the Task 1 rename. If it points elsewhere, fix that one line and re-run.

- [ ] **Step 2: Write the failing test**

Create `tests/api/test_spa_index.py`:
```python
import importlib

from fastapi.testclient import TestClient


def test_serves_index_when_dist_present(tmp_path, monkeypatch):
    # Isolate the DB exactly like conftest's client fixture, so create_app()'s
    # init_db() doesn't touch the real data/finance.db.
    from modules import database
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()

    from backend import main
    importlib.reload(main)  # rebuild module-level app against the patched DB_PATH

    # IMPORTANT: patch DIST_DIR *after* reload — reload recomputes DIST_DIR from
    # __file__, which would otherwise clobber an earlier patch.
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text(
        "<!doctype html><title>HomeFinance</title>", encoding="utf-8"
    )
    monkeypatch.setattr(main, "DIST_DIR", dist)

    # create_app() reads main.DIST_DIR at call time, so it sees the temp dist
    # and mounts StaticFiles at "/".
    client = TestClient(main.create_app())

    r = client.get("/")
    assert r.status_code == 200
    assert "HomeFinance" in r.text
    assert client.get("/api/health").json() == {"status": "ok"}
```

- [ ] **Step 3: Run it**

```bash
C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api/test_spa_index.py -v
```
Expected: PASS. If `GET /` returns 307 instead of 200, the `StaticFiles` mount didn't take — confirm `create_app()` references the module-level `DIST_DIR` at call time (it does today) and that the patch ran *after* the reload.

- [ ] **Step 4: Full API suite green**

```bash
C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest tests/api -q
```
Expected: `14 passed` (the 13 from Task 1 + this new test).

- [ ] **Step 5: Commit**

```bash
git add tests/api/test_spa_index.py
git commit -m "test(api): verify FastAPI serves built SPA index single-port"
```

---

### Task 3: Verify the Node.js toolchain (gate for Tasks 4–5)

**Why:** every web step (Vite scaffold, build, shadcn) needs Node/npm. They are already installed on this machine; this task just confirms they resolve before Tasks 4–5 begin.

**Files:** none (environment check only — nothing committed).

**Interfaces:**
- Produces: confirmation that `node` and `npm` resolve in a fresh shell. If a future shell can't find them, fallback absolute paths: `C:/Program Files/nodejs/node.exe`, `C:/Program Files/nodejs/npm.cmd`.

- [ ] **Step 1: Verify node + npm**

```bash
node -v && npm -v
```
Expected: `v24.16.0` (or similar ≥ 20) and `11.13.0` (or similar ≥ 10). If "not recognized" in this particular shell, retry once in a new tool call, or use the fallback paths above and prefix the npm commands in Tasks 4–5 accordingly. Do NOT install Node — it is already present.

- [ ] **Step 2: No commit** — environment check only. Proceed to Task 4.

---

### Task 4: Scaffold Vite + React + TypeScript in `web/`

**Files:**
- Create: `web/` (Vite `react-ts` template — `package.json`, `index.html`, `src/main.tsx`, `src/App.tsx`, `src/index.css`, `tsconfig.json`, `tsconfig.app.json`, `tsconfig.node.json`, `vite.config.ts`)
- Modify: `web/vite.config.ts` (dev proxy + path alias), `web/tsconfig.json` + `web/tsconfig.app.json` (alias), `.gitignore`

**Interfaces:**
- Produces: `npm --prefix web run dev` (Vite on `:5173`, proxies `/api` → `:8000`); `npm --prefix web run build` → `web/dist/index.html`. Path alias `@/` → `web/src/`. (The `@/lib/utils` `cn()` helper arrives in Task 5 via shadcn.)

- [ ] **Step 1: Create the Vite app**

From the worktree root:
```bash
npm create vite@latest web -- --template react-ts
npm --prefix web install
```

- [ ] **Step 2: Ignore build/deps**

Ensure the root `.gitignore` contains (append if missing):
```
web/node_modules/
web/dist/
```

- [ ] **Step 3: Configure Vite (proxy + alias)**

Overwrite `web/vite.config.ts`:
```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  server: {
    port: 5173,
    proxy: { "/api": { target: "http://localhost:8000", changeOrigin: true } },
  },
});
```

Add the alias to TypeScript so editors/`tsc` resolve `@/*`. In **both** `web/tsconfig.json` and `web/tsconfig.app.json`, add to `compilerOptions` (create the keys if absent):
```jsonc
"baseUrl": ".",
"paths": { "@/*": ["./src/*"] }
```

- [ ] **Step 4: Minimal app renders**

Replace `web/src/App.tsx`:
```tsx
export default function App() {
  return <div className="app-root">HomeFinance — Frosted Ledger (scaffold)</div>;
}
```
In `web/src/main.tsx`, remove the demo `import "./App.css"` if present (keep `import "./index.css"`). Delete the now-unused `web/src/App.css` so the build has no dangling import.

- [ ] **Step 5: Build succeeds**

```bash
npm --prefix web run build
ls web/dist/index.html
```
Expected: build completes; `web/dist/index.html` exists.

- [ ] **Step 6: Dev proxy sanity (optional but recommended)**

Start the API and Vite, confirm the proxy reaches the API:
```bash
VPY="C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe"
"$VPY" -m uvicorn backend.main:app --port 8000 --log-level warning &
APID=$!
npm --prefix web run dev &
VPID=$!
curl -s --retry 20 --retry-connrefused --retry-delay 1 http://localhost:5173/api/health; echo
kill $APID $VPID
```
Expected: `{"status":"ok"}` (proxied through Vite). Then stop both.

- [ ] **Step 7: Commit** (node_modules/dist excluded by .gitignore)

```bash
git add web .gitignore
git commit -m "feat(web): scaffold Vite + React + TS app with API dev-proxy"
```

---

### Task 5: Tailwind v4 + shadcn/ui (slate) + "Frosted Ledger" tokens

**Files:**
- Modify: `web/vite.config.ts` (add Tailwind plugin), `web/src/index.css` (Tailwind import + brand tokens), `web/src/main.tsx` (font import), `web/package.json` (deps)
- Create (via shadcn CLI): `web/components.json`, `web/src/lib/utils.ts`, `web/src/components/ui/*`

**Interfaces:**
- Produces: shadcn components installable into `web/src/components/ui`; the `cn()` helper at `@/lib/utils`; the full Frosted Ledger CSS-variable palette (light + `.dark`) available app-wide; Plus Jakarta Sans as the default font. (Mapping these brand tokens onto shadcn's `--primary`/`--chart-*` and wiring the dark-mode toggle is **Plan 3**.)

- [ ] **Step 1: Install + wire Tailwind v4**

```bash
npm --prefix web install tailwindcss @tailwindcss/vite
```
Add the plugin to `web/vite.config.ts`: `import tailwindcss from "@tailwindcss/vite";` and add `tailwindcss()` to the `plugins` array (so it reads `plugins: [react(), tailwindcss()]`).

- [ ] **Step 2: Initialize shadcn (slate base)**

First consult the shadcn MCP (now available — Node is installed) to confirm the current Tailwind-v4 init flow:
`search_items_in_registries` / `get_add_command_for_items`. Then run a non-interactive init:
```bash
cd web && npx shadcn@latest init -d -b slate ; cd ..
```
(`-d` accepts defaults, `-b slate` sets the base color. If it still prompts: TypeScript = yes, style = "new-york", base color = "slate", CSS file = `src/index.css`, CSS variables = yes, aliases `@/components` and `@/lib/utils`.) This writes `web/components.json` and `web/src/lib/utils.ts`, and rewrites `web/src/index.css` with `@import "tailwindcss";` plus shadcn's `:root`/`.dark` base layers.

- [ ] **Step 3: Add core components**

```bash
cd web && npx shadcn@latest add button card separator badge avatar dropdown-menu tabs skeleton tooltip sonner ; cd ..
```
These land in `web/src/components/ui/`. (Sidebar and data-table components are added in Plan 3 when the shell is built.)

- [ ] **Step 4: Add the display font**

```bash
npm --prefix web install @fontsource-variable/plus-jakarta-sans
```
At the top of `web/src/main.tsx` add: `import "@fontsource-variable/plus-jakarta-sans";`

- [ ] **Step 5: Append the Frosted Ledger brand tokens**

Append to the end of `web/src/index.css` (after shadcn's generated layers — these are additive brand custom-properties; they don't fight shadcn's slate theme):
```css
/* ---- Frosted Ledger brand tokens (spec §3). Light. ---- */
:root {
  --font-sans: "Plus Jakarta Sans Variable", ui-sans-serif, system-ui, sans-serif;

  /* surfaces */
  --fl-canvas: #E5E6EA;
  --fl-frame:  #F6F7F9;
  --fl-card:   #FFFFFF;
  --fl-line:   #ECEDF0;
  --fl-ink:    #16181D;
  --fl-muted:  #8A8F98;

  /* persona inks */
  --persona-you:        #3B82F6;
  --persona-you-deep:   #2563EB;
  --persona-spouse:     #EC4899;
  /* Joint = blue→pink gradient */
  --persona-joint: linear-gradient(90deg, var(--persona-you), var(--persona-spouse));

  /* money semantics */
  --pos: #22C55E; /* income / positive */
  --neg: #EF4444; /* over-budget / negative */
  --saved: #A855F7; /* tertiary / "saved" series */

  /* AI Insights showpiece gradient (used only on that one card) */
  --showpiece: linear-gradient(120deg, #FDBA74, #F472B6, #A855F7, #3B82F6);

  /* active persona accent — swapped at runtime by the persona context in Plan 3 */
  --persona: var(--persona-you);

  --radius-card: 18px;
}

/* ---- After-dark token set, defined up front (spec §13). Toggle wired in Plan 3. ---- */
.dark {
  --fl-canvas: #0B0C0F;
  --fl-frame:  #16181D;
  --fl-card:   #1C1F26;
  --fl-line:   #2A2E37;
  --fl-ink:    #F6F7F9;
  --fl-muted:  #8A8F98;
  /* persona inks, money semantics, showpiece and --persona inherit from :root */
}

body {
  font-family: var(--font-sans);
  font-variant-numeric: tabular-nums; /* ledger-aligned figures */
}
.frosted-canvas { background: var(--fl-canvas); }
.frosted-card {
  background: var(--fl-card);
  border: 1px solid var(--fl-line);
  border-radius: var(--radius-card);
  box-shadow: 0 10px 30px -22px rgba(22, 24, 29, .35);
}
```

- [ ] **Step 6: Verify the build still succeeds**

```bash
npm --prefix web run build && ls web/dist/index.html
```
Expected: build OK, `web/dist/index.html` present.

- [ ] **Step 7: Commit**

```bash
git add web
git commit -m "feat(web): Tailwind v4 + shadcn (slate) + Frosted Ledger tokens"
```

---

## Self-Review

**1. Spec coverage** (this wave = spec §2 frontend toolchain + §3 identity foundation + the scaffold half of §11 wave 2):
- §2 Vite SPA + dev proxy (`/api` → `:8000`) → Task 4. ✓
- §2 single-port FastAPI serving `web/dist` → Task 2 (dist-present test) + existing `test_spa_serving.py` (dist-absent). ✓
- §2 `app/` package corrected to `backend/` (collision fix) → Task 1. ✓
- §3 shadcn slate base + full brand CSS-variable palette + Plus Jakarta Sans + tabular numerals → Task 5. ✓
- §13 dark-mode token set defined up front (`.dark` block) → Task 5. ✓ (toggle = Plan 3)
- Node toolchain present (v24 / npm 11) — Task 3 verifies it (no install needed). ✓
- **Deferred to Plan 3** (explicit): the app shell (sidebar + persona context + theme toggle), routing, mapping brand tokens onto shadcn `--primary`/`--chart-*`, and the Overview page wired to `/api/overview`. (spec §4, §5, §9; §11 wave-2 remainder.)

**2. Placeholder scan:** all config/CSS/test contents are concrete. The two CLI-generated steps (shadcn `init`/`add`) intentionally do not transcribe generated component source — that is produced by the official CLI, with the shadcn MCP named as the reference. No TBD/TODO.

**3. Type/path/fact consistency:**
- uvicorn target `backend.main:app` (Task 1) matches `run_api.py` and conftest `from backend import main`. ✓
- `DIST_DIR` resolves to `<repo>/web/dist` (Task 2) — exactly what Task 4 builds. ✓
- The `@/` alias is defined identically in `vite.config.ts` and `tsconfig*.json` (Task 4) and consumed by shadcn (Task 5). ✓
- Task 2's test patches `DIST_DIR` **after** `importlib.reload(main)` (reload recomputes it from `__file__`) and isolates `DB_PATH` like conftest — verified against `backend/main.py` (reads `DIST_DIR` at `create_app()` call time) and `modules/database.py` (`DB_PATH` read at call time in `get_conn`/`init_db`). ✓
- Test counts: 13 collected today → Task 1 keeps 13 → Task 2 adds 1 → `14 passed`. ✓
- The pre-existing `GET /` → `/docs` redirect fires only when `web/dist` is absent, so it does not affect Task 2's dist-present assertion nor `test_spa_serving.py`'s 404-on-unknown-route assertion. ✓

**Dependency order:** Task 1 → Task 2 are Node-free (run first). Task 3 verifies Node and **gates** Tasks 4 → 5.
