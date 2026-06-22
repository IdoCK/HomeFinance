# UI Rewrite — Plan 12: Align main's features into the design system

**Context:** `origin/main` was merged into `feature/ui-rewrite` (merge commit). It brought 5
engine capabilities not yet in the React UI. This plan surfaces all five, each Frosted-Ledger
styled, persona-aware, TDD, atomic commits. Engine is already merged — do NOT modify `modules/`.

Already covered by the rewrite (no work): recurring-detection (shared code → Recurring page),
people rename/safety (Settings + people router 409).

## Working Context
- Worktree branch `feature/ui-rewrite` (post-merge). npm via PowerShell; pytest via venv python.
- Engine (reuse as-is): `analytics.spending_alerts(txns)`, `analytics.reconcile(rows)`,
  `analytics.find_transfer_pairs(txns)`, `analytics.budget_status(txns,budgets,parents)` (already
  rolls up parents), `db.category_parents/upsert_category(...,parent)`,
  `db.create_event/list_events/delete_event/event_transaction_ids/set_event_tags`.

---

### Feature A: Spending alerts on Overview
- **Backend:** extend `GET /api/overview` → add `alerts: analytics.spending_alerts(txns)` (list of
  `{category,current,baseline,delta,pct,direction,new}`). Backward-compatible key.
- **Client:** add `alerts` to `Overview` type.
- **UI:** Overview renders alert chips ("Dining ↑62% vs usual", red up / green down / "new"),
  hidden when none. Fits the "are we okay this month" thesis.
- **Tests:** overview test asserts `alerts` present; Overview.test renders a chip.
- Commits: `feat(api): spending alerts on overview` · `feat(web): overview alert chips`.

### Feature B: Statement reconciliation on Net Worth
- **Backend:** `GET /api/networth/reconcile?person_id=` → `analytics.reconcile(db.get_transactions(pid))`
  (None when no running balances → `{reconcilable: false}`).
- **Client:** `getReconciliation(personId)`.
- **UI:** Net Worth panel — ties-out badge (✓ balances / discrepancy $X), begin/end/computed, chain breaks.
- **Tests:** router (seeded balances → ok; no balance → not reconcilable); client; NetWorth panel.
- Commits: `feat(api): reconciliation endpoint` · `feat(web): reconciliation client` · `feat(web): Net Worth reconciliation panel`.

### Feature C: Transfer-pair matching on Transactions
- **Backend:** `GET /api/transactions/transfers?person_id=` → `analytics.find_transfer_pairs(txns)`.
  (Route ordering: declare before `/{id}` if any — transactions router uses PATCH `/{id}`, GET is base, safe.)
- **Client:** `getTransferPairs(personId)`; reuse `updateTransaction` to exclude.
- **UI:** Transactions banner — "N transfer pairs detected"; each pair shows both sides + an
  "Exclude both" action (PATCH included=false on out_id & in_id), then refetch.
- **Tests:** router (seeded cross-person pair → 1 pair); client; Transactions banner + exclude call.
- Commits: `feat(api): transfer-pairs endpoint` · `feat(web): transfer client` · `feat(web): Transactions transfer-pairs banner`.

### Feature D: Budgets parent-rollup (assign parents in Settings)
- Backend already rolls up (`budget_status` + `category_parents`). Gap = no way to set a
  category's parent in the UI, and the client drops `parent`.
- **Client:** `upsertCategory` sends optional `parent`.
- **UI:** Settings category rows gain an inline "parent" field (blur → upsert with parent). A
  budget set on a parent name then rolls up its children automatically.
- **Tests:** client sends parent; Settings edits parent → upsertCategory called with it.
- Commit: `feat(web): edit category parent in Settings (enables budget rollups)`.

### Feature E: Event tagging (new Events page + tag from Transactions)
- **Backend:** new `backend/api/events.py` — `GET /events?person_id=`, `POST /events`,
  `DELETE /events/{id}`, `GET /events/{id}/transactions`, `PUT /events/{id}/transactions`
  (`set_event_tags`). Schemas `EventCreate`, `EventTags`. Event spend = sum of tagged txns
  (computed client-side from tagged ids, or a small summary in the GET). Keep v1 = explicit
  membership; defer rule-based auto-membership (engine `rule`/`event_mask`).
- **Client:** `getEvents/createEvent/deleteEvent/getEventTransactions/setEventTags`.
- **UI:** new `/events` page (nav added after Net Worth) — list events with tagged-spend total,
  create (name + kind), delete, and a member editor (pick from the person's transactions).
  **IA note:** adds a 10th nav item — a deliberate deviation from the locked 9-page IA to
  surface a net-new capability.
- **Tests:** events router CRUD + tagging; client; Events page renders/creates/tags.
- Commits: `feat(api): events router` · `feat(web): events client` · `feat(web): Events page + nav`.

## Self-Review
All 5 main capabilities surfaced; engine untouched; persona-aware; deferrals (event rules) noted.
Update CUTOVER.md debt ledger + memory after. Final: full pytest + web + build green.
