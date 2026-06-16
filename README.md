# Household Finance Dashboard

A local, private, two-person finance dashboard. Parses your CSV/spreadsheet
exports (Amazon, credit card, bank), tracks custom spending categories and
savings goals, draws charts, and generates AI insights from **anonymized
aggregates only**.

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

## Run
```bash
streamlit run app.py
```
Opens at http://localhost:8501

## Enable AI insights (optional)
```bash
export ANTHROPIC_API_KEY=sk-ant-...   # Windows: set ANTHROPIC_API_KEY=...
```
Without a key, the app still works — the AI tab just shows you what *would* be
sent instead of calling out.

## Local parsing agent (handles any file format)

Every uploaded file is read by a **local AI agent** running on your machine via
[Ollama](https://ollama.com) — no web access. It inspects each file and figures
out the columns, separators, header position, date format, and sign convention
on its own, so credit card, bank, and Amazon exports in totally different
layouts all just work. It also handles separate debit/credit columns and junk
preamble rows. The same local agent can auto-categorize merchants by name
(Chewy → Dog, Chipotle → Eating Out) from the Categories tab.

### One-time setup
```bash
# 1. Install Ollama from https://ollama.com
# 2. Pull the model (a few GB, downloaded once):
ollama pull qwen2.5
```
Ollama then serves locally at http://localhost:11434 and needs no internet after
the pull. The Import tab shows a 🟢/🔴 indicator for whether the agent is ready.


- **Amazon**: amazon.com/gp/b2b/reports → "Items" report → download CSV
- **Credit card / bank**: export transactions as CSV from your provider
- Go to the **Import** tab (in a person's view), pick the source, upload.

## Two people
Use the sidebar to switch between each person and the **Household** view (which
merges both for joint spending, savings, and shared goals). Rename "You" /
"Spouse" later if you want — they're just seeded defaults.

## Categories
Define categories with comma-separated keywords (e.g. `groceries` →
`whole foods, trader joe, grocery`). Imports auto-tag matching transactions.
