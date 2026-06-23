# Design: HomeFinance Expert Agents

**Date:** 2026-06-23
**Status:** Approved (design phase)
**Topic:** Four project-scoped advisory subagents for the HomeFinance app

## Goal

Add four domain-expert subagents to `.claude/agents/` that act as **advisory/review
consultants** for HomeFinance. They analyze the real code and data, then return
structured findings and recommendations. They do **not** write production code — the
main session does the implementing. They exist to raise the financial rigor and
product quality of the app by bringing focused domain expertise to bear on demand.

The app's north-star reframing is unchanged: *"are we okay this month, and are we
hitting our goals?"* Every agent serves that question from its own angle.

## Locked decisions

- **Role:** Advise & review only. Read-only tooling (no `Edit`/`Write`).
- **Scope:** Project-scoped — committed to the repo, tuned to HomeFinance's schema,
  `modules/` engine, `backend/api/` routers, and `web/` frontend.
- **Specialty split:** Personal-finance split (Home / Growth / Accounting) + a
  dedicated dashboard & graphs expert.
- **Model:** `opus` for all four.
- **Tools:** `Read, Grep, Glob, Bash, WebSearch, WebFetch`. `Bash` is for running the
  test suite and read-only DB/data queries; web tools are for current tax rules,
  FX/market facts, and best-practice references. No file mutation tools.

## Project grounding (shared by all agents)

- **Architecture:** Python engine in `modules/` (`analytics.py`, `database.py`,
  `fx.py`, `keywords.py`, `agent_parser.py`, `formats.py`, `parsing.py`,
  `ai_insights.py`) → thin FastAPI layer in `backend/api/` → React (Vite) + shadcn
  SPA in `web/`. SQLite at `data/finance.db`.
- **Two-person model:** You = blue `#3B82F6`, Spouse = pink `#EC4899`, Joint =
  both/merged. Persona is a `person_id` (omitted/None = Joint). Visual identity is
  "Frosted Ledger."
- **Multi-currency:** canonical pivot + default display = USD; `amount_base` holds
  the USD value; FX via Frankfurter (ECB), cached in `fx_rates`; display toggle
  `$ USD | ₪ ILS`. See `modules/fx.py`, `backend/api/fx.py`, `web/src/lib/currency.tsx`.
- **Tests:** `venv/Scripts/python.exe -m unittest discover -s tests` for the engine;
  `pytest` for `tests/api/`; Vitest for `web/`.

## The four agents

### 1. `home-finance-advisor` — day-to-day money health
- **Owns:** budgeting, cashflow, spending health, the present-month "are we okay"
  question.
- **Reviews:** `analytics.budget_status`, `monthly_savings` (savings_rate +
  complete flag), `latest_complete_month`, `spending_alerts`, recurring/committed
  spend, partial-cycle warnings. Backend: `backend/api/budgets.py`, `overview.py`,
  `recurring.py`. Frontend: `Overview.tsx`, `Budgets.tsx`, `Recurring.tsx`.
- **Lens:** Is the household's current-month picture truthful, complete, and
  actionable? Are budgets and alerts surfacing the right things?

### 2. `growth-finance-advisor` — wealth building over time
- **Owns:** net worth trajectory, savings rate as a growth metric, goals/targets,
  investing and long-term compounding, the "are we building wealth" question.
- **Reviews:** `analytics.net_worth` / `net_worth_trend` (forward-fill), `goals`
  progress, savings-rate math. Backend: `backend/api/networth.py`, `goals.py`.
  Frontend: `NetWorth.tsx`, `Goals.tsx`.
- **Lens:** Does the app help the household see and improve its long-term
  trajectory? Where does it under-serve the future (e.g., no investing/return
  modeling, no goal pacing)?

### 3. `accounting-advisor` — books integrity
- **Owns:** bookkeeping correctness, reconciliation, double-entry thinking,
  transfer/refund netting, categorization hygiene, multi-currency correctness,
  tax-relevant hygiene.
- **Reviews:** `analytics.reconcile` (computed vs statement balance),
  `find_transfer_pairs`, refund netting (`_split`), the `included` internal-transfer
  flag, `amount_base`/`fx.py` conversion correctness, category taxonomy. Backend:
  `backend/api/transactions.py`, `networth.py` (reconcile), `fx.py`, `categories.py`,
  `vendors.py`.
- **Lens:** Do the books tie out? Is every dollar/shekel classified once, netted
  correctly, and converted correctly? This is the financial-correctness bug catcher.

### 4. `dashboard-graphs-advisor` — data viz & dashboards
- **Owns:** chart correctness and communicative effectiveness, dashboard
  information architecture, the Frosted Ledger visual identity, chart
  accessibility, picking the right chart for the question.
- **Reviews:** `web/src/components/charts/` (`area-chart`, `bar-chart`,
  `line-chart`, `stacked-bars`, `dot-matrix`, `_svg`), and how each page deploys
  them (`Overview.tsx`, `Analysis.tsx`, etc.). Checks persona color usage
  (You=blue/Spouse=pink/Joint), big-bold-number hierarchy, axis/scale honesty,
  empty/partial states.
- **Lens:** Does each visualization actually tell the financial story it should,
  legibly and honestly?

## Shared agent-file structure

Each `.claude/agents/<name>.md` contains:

1. **Frontmatter:** `name`, `description` (one line + concrete trigger examples so
   the agent auto-dispatches well), `tools` (the read-only set above), `model: opus`.
2. **Identity + mandate:** who the agent is and the single question it owns.
3. **HomeFinance grounding:** the specific files/tables/functions it cares about,
   the reframing goal, the two-person + multi-currency models (condensed from the
   shared grounding above).
4. **Review method:** an ordered checklist of what it inspects, starting from the
   engine (`modules/`) outward to API and UI, always citing real code as evidence.
5. **Output format:** structured findings — each with **severity**
   (blocker / concern / suggestion), **location** (`file:line`), **what's wrong /
   missing**, and a **recommendation**. End with a short prioritized summary.
6. **Lane discipline:** advise only; cite evidence from real code (no hand-waving);
   do not write production code; defer out-of-scope items to the right sibling agent.

## Cross-cutting boundary rule

Overlaps are explicit. Each prompt names the other three and states hand-offs:

- **Savings rate** touches Home (this month) and Growth (trajectory) → Home owns the
  monthly number; Growth owns the trend and what to do about it.
- **Categorization** touches Accounting (correctness) and Home (budget impact) →
  Accounting owns whether it's classified correctly; Home owns whether the budget
  view is useful.
- **Net worth charts** touch Growth (the metric) and Dashboard (the rendering) →
  Growth owns whether the number/trend is right; Dashboard owns whether the chart
  communicates it.
- **FX/`amount_base`** is Accounting's correctness call; any agent noticing a
  currency display issue routes it there.

## Out of scope (YAGNI)

- No write/implementation capability in the agents themselves.
- No new slash commands or orchestration layer — they're plain subagents dispatched
  on demand.
- No general-purpose (cross-project) variants; these are HomeFinance-tuned.

## Success criteria

- Four agent files exist under `.claude/agents/` with valid frontmatter and load as
  selectable subagents.
- Each agent, when dispatched on a relevant question, returns evidence-cited,
  severity-ranked findings grounded in real files — not generic finance advice.
- Boundaries route cleanly: an out-of-scope question is handed off, not answered
  vaguely.
