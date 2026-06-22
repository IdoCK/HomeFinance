# Cutover — Streamlit → React SPA (spec §11 wave 6)

The React + FastAPI rewrite is feature-complete: every Streamlit capability has a
page (Overview, Transactions, Budgets, Recurring, Goals, Net Worth, Import, AI
Insights, Settings), each backed by a thin router over the unchanged engine and
the same `data/finance.db`.

This doc is the final wave: **verify parity against the old app, then retire `app.py`.**

## Why `app.py` is still here
Retiring Streamlit is deliberately the *last* step and is left for you to pull the
trigger on, because parity must be verified against **real data** — something that
can't be done in CI or an empty worktree DB:

- The worktree's `data/finance.db` is empty; the dev server shows empty states.
- Import + AI Insights need **Ollama** running / an **ANTHROPIC_API_KEY** to
  exercise end-to-end; both degrade gracefully but aren't fully live in tests.

## Parity checklist (run against a copy of your real `data/finance.db`)
Point the API at real data, `npm --prefix web run build`, `python run_api.py`, then:

- [ ] **Overview** — KPIs, cash-flow, savings rate, who-spent-what match the old dashboard.
- [ ] **Transactions** — list, inline category edit, include toggle, filters, persona braid.
- [ ] **Budgets** — per-category pace meters; cap edit/add/delete; Joint = household set.
- [ ] **Recurring** — committed monthly, charge list, anomalies.
- [ ] **Goals** — progress, inline saved-amount edit, add/delete.
- [ ] **Net Worth** — hero, delta, trend sparkline, accounts CRUD.
- [ ] **Import** — Ollama chip; parse a real export; review; commit; dedup on re-import.
- [ ] **AI Insights** — payload preview matches; generate (with a key) returns coaching text.
- [ ] **Settings** — rename people; per-person categories + vendor groups CRUD; **category parent groups**.
- [ ] **Overview alerts** — spending-alert chips vs the rolling baseline (cashflow-alerts).
- [ ] **Net Worth reconciliation** — statements tie out / discrepancy (statement-reconciliation).
- [ ] **Transactions transfer pairs** — detected pairs + "exclude both" (transfer-matching).
- [ ] **Events** — create/delete events, tag transactions, tagged-spend totals (event-tagging).

> All of `origin/main`'s engine features are now surfaced in the React UI (Plan 12 alignment).
> The merge brought recurring (already a page), people-safety (Settings), and the five above.

## Retire `app.py` (after the checklist passes)
Streamlit-only bits that have no React home and can go with it:
- `app.py` (the whole Streamlit UI; preserved in git history).
- `streamlit` in `requirements.txt`.
- Any Streamlit-only helpers in `app.py` not used by `modules/` or `backend/`
  (the engine in `modules/` is shared and must stay).

```bash
git rm app.py
# edit requirements.txt: drop streamlit
git commit -m "chore: retire legacy Streamlit app after React parity"
```

Keep `modules/`, `backend/`, `web/`, `run_api.py`, and `data/finance.db`.

## Deferred from the page builds (debt ledger)
Tracked so they aren't lost — none block cutover:
- Import: progress streaming (SSE/polling), "learn a new format" UI, keyword-rule
  learning on commit, statement-balance → Net Worth account refresh, drag-and-drop.
- AI Insights: rich markdown rendering of the result; Overview "latest insight" teaser.
- Backend foundation: `get_transaction(txn_id)` helper to collapse the PATCH double-scan.
- Events (Plan 12): rule-based auto-membership (engine `rule`/`event_mask`) — v1 is explicit
  tagging only; date/kind fields aren't editable in the UI yet.
- Budgets parent-rollup: parents are assignable in Settings, but the Budgets page doesn't yet
  render a parent→children grouped view (a budget on a parent name still rolls up correctly).
