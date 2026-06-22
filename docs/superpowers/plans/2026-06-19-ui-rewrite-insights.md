# UI Rewrite — Plan 10: AI Insights Page Implementation Plan

**Goal:** Replace the `/insights` placeholder with the glassy-gradient showpiece that turns
anonymized aggregates into Anthropic coaching text — a new thin `insights` router over
`modules/ai_insights.py`, the API client, and `pages/Insights.tsx`. Design:
`docs/superpowers/specs/2026-06-19-insights-page-design.md`.

## Working Context
- Worktree `.claude/worktrees/ui-rewrite`, branch `feature/ui-rewrite`. Depends on Plans 1–9.
- npm/npx via PowerShell (`$env:Path = "C:\Users\lahat\node\node-v24.16.0-win-x64;" + $env:Path`), `npm --prefix web ...` from worktree root.
- pytest via `C:/Users/lahat/Documents/Claude/HomeFinance/venv/Scripts/python.exe -m pytest ...`.
- Engine (do NOT modify): `ai_insights.build_anonymized_summary(label, txns, goals, analytics)`,
  `ai_insights.preview_payload(summaries)`, `ai_insights.get_insights(summaries)`;
  `db.list_people`, `db.get_transactions(pid)`, `db.get_goals(pid|None)`; `modules.analytics`.

### Task 1: Insights router (backend)
- Create `backend/api/insights.py` (prefix `/insights`): a `_summaries(person_id)` helper
  (single "Person A" for an int; household Person A/B + "Household (shared goals)" for None);
  `GET /preview` → `{payload, has_key}`; `POST /generate` → `{text}`. Body schema `InsightsRequest`.
- Register in `backend/main.py`.
- `tests/api/test_insights.py`: preview returns a payload string + `has_key` bool; payload
  contains no raw merchant/transaction leak (spot-check it's valid JSON aggregates); generate
  returns a `text` string (no key → preview-mode message; still 200).
- Commit: `feat(api): insights router (anonymized preview + generate)`.

### Task 2: Insights API client (frontend)
- `web/src/lib/api.ts`: `type InsightsPreview = { payload: string; has_key: boolean }`;
  `getInsightsPreview(personId?)` → GET; `generateInsights(personId?)` → POST `{text}`.
- `web/src/lib/api.test.ts`: URL/method/body assertions for both.
- Commit: `feat(web): insights API client`.

### Task 3: Insights page
- `web/src/pages/Insights.tsx`: glassy gradient hero (showpiece gradient), Generate button
  (disabled + note when `!has_key`), `<details>` payload disclosure, pre-wrapped result card,
  loading state. Persona via `usePersona().personId`.
- `web/src/pages/Insights.test.tsx`: renders hero + payload after load; Generate calls
  `generateInsights` and shows the returned text; button disabled w/ note when `has_key` false.
- Commit: `feat(web): AI Insights page (glassy showpiece + privacy preview)`.

### Task 4: Wire `/insights` route
- `web/src/routes.tsx`: import + swap placeholder. Build + full suite. Commit `feat(web): wire /insights route`.

## Self-Review
Privacy preview shown before generate ✓; persona household vs single ✓; graceful no-key ✓;
gradient reserved to this page ✓; engine untouched ✓.
