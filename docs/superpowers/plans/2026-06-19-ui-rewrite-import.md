# UI Rewrite — Plan 11: Import Wizard Implementation Plan

**Goal:** Replace the `/import` placeholder with a 3-step wizard over a new thin `import` router.
Design: `docs/superpowers/specs/2026-06-19-import-page-design.md`. Lean v1 — deferrals listed in
the design's "Out of scope".

## Working Context
- Worktree `.claude/worktrees/ui-rewrite`, branch `feature/ui-rewrite`. Depends on Plans 1–10.
- npm via PowerShell; pytest via the venv python (see prior plans).
- Engine (do NOT modify): `agent_parser.check_ollama()`, `agent_parser.parse_file_with_agent(
  bytes, filename, source, categorize_fn, category_rules)`; `parsing.categorize`;
  `db.get_categories`, `db.get_import`, `db.add_transactions`, `db.record_import`.
- `category_rules(pid)` = `[(c["name"], (c["keywords"] or "").split(",")) for c in db.get_categories(pid)]`.

### Task 1: Import router (backend)
- Create `backend/api/imports.py` (prefix `/import`): `GET /status`, `POST /parse` (multipart),
  `POST /commit`. `ImportRow` + `ImportCommit` schemas. Compute `file_hash` with hashlib.sha256.
  Parse delegates to `agent_parser.parse_file_with_agent` (call via the module so tests can
  monkeypatch it without Ollama). Register in `backend/main.py`.
- `tests/api/test_imports.py`: status returns `{ok: bool, message: str}` (200 even offline);
  parse (monkeypatched agent) returns rows + file_hash; commit inserts rows (assert via
  `/api/transactions`); re-parse of a committed hash → `already_imported: true`.
- Commit: `feat(api): import router (status + parse + commit)`.

### Task 2: Import API client (frontend)
- `web/src/lib/api.ts`: `type ImportRow`, `type ImportParseResult`, `type OllamaStatus`;
  `getOllamaStatus()`; `parseImport(file, source, personId)` (FormData POST — no JSON header);
  `commitImport({personId, filename, fileHash, source, rows})`.
- `web/src/lib/api.test.ts`: assert FormData fields + URL for parse, JSON body for commit, URL for status.
- Commit: `feat(web): import API client`.

### Task 3: Import wizard page
- `web/src/pages/Import.tsx`: `step` state machine (upload → review → done); persona gate for
  Joint; Ollama chip; source select; review table (editable category + include); warnings banner;
  commit. `pages/Import.test.tsx`: persona gate; upload→parse advances to review with rows;
  commit calls `commitImport` and shows done; already-imported notice.
- Commit: `feat(web): Import wizard (upload → review → commit)`.

### Task 4: Wire `/import` route
- `web/src/routes.tsx`: import + swap placeholder. Build + full suite. Commit `feat(web): wire /import route`.

## Self-Review
Per-person gate ✓; agent reused, engine untouched ✓; dedup via hash ✓; deferrals documented ✓;
parse testable without Ollama (monkeypatch) ✓.
