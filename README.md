# Household Finance Dashboard

A local, private, two-person finance dashboard. Parses your CSV/spreadsheet
exports (Amazon, credit card, bank), tracks custom spending categories and
savings goals, draws charts, and generates AI insights from **anonymized
aggregates only**.

The UI is a **React single-page app** (the "Frosted Ledger" design) served by a
thin **FastAPI** layer that reuses the existing Python engine (`modules/`) and
the same `data/finance.db`. The legacy Streamlit app is deprecated — see below.

## What stays private
All raw data lives in `data/finance.db` on your machine. The only thing ever
sent to an AI model is aggregated numbers — category totals, monthly
spend/savings, and goal-progress percentages. No merchant names, no raw
transactions, no account numbers, no real names, no goal notes. You can preview
the exact payload before sending.

## Setup
```bash
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

## Run (production / everyday use)
Build the frontend once, then start the API — it serves the built SPA and the
JSON API from a single process on one port. No Node runtime needed to *run*.

```bash
npm --prefix web install        # first time only
npm --prefix web run build      # emits web/dist
python run_api.py               # http://localhost:8000
```
Open http://localhost:8000.

## Run (frontend development)
Two processes, with hot reload. Vite proxies `/api/*` to the API.

```bash
python run_api.py                       # API on :8000
npm --prefix web run dev                # SPA on :5173 (proxies to :8000)
```
Open http://localhost:5173.

### Tests
```bash
venv/Scripts/python -m pytest tests/api -q   # FastAPI routers
venv/Scripts/python -m unittest discover -s tests   # engine
npm --prefix web test                        # frontend (Vitest)
```

## Enable AI insights (optional)
```bash
export ANTHROPIC_API_KEY=sk-ant-...   # Windows: set ANTHROPIC_API_KEY=...
```
Without a key, the **AI Insights** page still works — it shows exactly what
*would* be sent (the anonymized payload) instead of calling out.

## Local parsing agent (handles any file format)
Every uploaded file is read by a **local AI agent** running on your machine via
[Ollama](https://ollama.com) — no web access. It inspects each file and figures
out the columns, separators, header position, date format, and sign convention
on its own, so credit card, bank, and Amazon exports in totally different
layouts all just work. It also handles separate debit/credit columns and junk
preamble rows. The same local agent can auto-categorize merchants by name
(Chewy → Dog, Chipotle → Eating Out).

### One-time setup
```bash
# 1. Install Ollama from https://ollama.com
# 2. Pull the model (a few GB, downloaded once):
ollama pull qwen2.5
```
Ollama then serves locally at http://localhost:11434 and needs no internet after
the pull. The **Import** page shows a 🟢/🔴 indicator for whether the agent is ready.

### Importing
- **Amazon**: amazon.com/gp/b2b/reports → "Items" report → download CSV
- **Credit card / bank**: export transactions as CSV from your provider
- Open the **Import** page in a person's view (Ido or Aviv), pick the source,
  upload, review the parsed rows, and commit.

## Two people
Use the sidebar persona switch (Ido / Aviv / **Joint**). Joint merges both for
shared spending, savings, and goals. Rename the two members anytime on the
**Settings** page — "Ido" / "Aviv" are just seeded defaults.

## Categories & vendor groups
On **Settings**, define per-person categories with comma-separated keywords (e.g.
`Groceries` → `whole foods, trader joe, grocery`). Imports auto-tag matching
transactions; the local agent infers the rest.

## Pages
Overview · Transactions · Budgets · Recurring · Goals · Net Worth · Import ·
AI Insights · Settings.

---

## Legacy: Streamlit app (deprecated)
The original UI was a Streamlit app (`app.py`). It is **deprecated** and will be
removed once the React UI is validated against your real data. It still runs
against the same database if you need it during the transition:

```bash
streamlit run app.py            # http://localhost:8501
```

See `docs/superpowers/CUTOVER.md` for the parity checklist and the plan to
retire `app.py`.
