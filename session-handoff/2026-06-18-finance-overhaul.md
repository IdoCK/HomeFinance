# Session handoff — HomeFinance overhaul (2026-06-18)

Compacted context so a **new session can continue seamlessly**. Read this top to bottom.

---

## 1. Project & environment
- **App:** local, private, two-person household finance dashboard. Streamlit + SQLite, local **Ollama** (qwen2.5) for file-format inference / AI categorization, optional **Claude API** for insights.
- **Repo:** `C:\Users\lahat\Documents\Claude\HomeFinance` — git repo, remote `origin` = https://github.com/IdoCK/HomeFinance.git, branch **main**.
- **Python:** venv at `venv\Scripts\python.exe` (Python 3.12). Deps in `requirements.txt` (streamlit, pandas, openpyxl, anthropic, altair, pytest).
- **Run the app:** `streamlit run app.py` → http://localhost:8501 (we run headless: `.\venv\Scripts\streamlit.exe run app.py --server.headless true`).
- **Run tests:** `.\venv\Scripts\python.exe -m pytest -q` → **64 passing**.
- **Boot check (no browser):** `from streamlit.testing.v1 import AppTest; AppTest.from_file('app.py').run()` — assert `.exception is None`. To test Household view: set the sidebar radio whose options include "Household".
- **Sample data:** `C:\Users\lahat\Downloads\May2026_bankstatement.csv` (has `Running Bal.`), `May2026_creditcard.csv` (no balance). Also `sample_data/`.
- **DB:** `data/finance.db` already has ~150 imported rows (You/Spouse). Schema auto-migrates on `init_db()`.

## 2. Git state (IMPORTANT)
- **HEAD = `3f30f8d`** "Add net worth tracking (Wave 2); overhaul checkpoint with tests" — contains W1 (savings rate/partial-month), W2 (net worth), keywords.py refactor, earlier tests. (Committed by a parallel agent.)
- **Uncommitted working-tree changes from THIS session (not yet committed/pushed):**
  - Modified: `app.py`, `modules/analytics.py`, `modules/database.py`, `modules/agent_parser.py`, `requirements.txt`
  - New (untracked): `tests/test_advanced_analytics.py`
- Nothing has been committed by me this session. **The user manages git/push** (coordinating with another agent on the remote). Do NOT push unless asked. If continuing, consider committing this work to avoid loss/overwrite — ask first.

## 3. How the app is structured
Tabs (in `app.py`): **📊 Dashboard · 📈 Analysis · 📥 Import · 🏷️ Categories · 🎯 Goals · 💵 Net Worth · 🤖 AI Insights**. Sidebar radio switches **You / Spouse / Household** (`view`). Per-view scoping helpers: `person_id_for_view`, `transactions_for_view`, `goals_for_view`, `accounts_for_view`, `snapshots_for_view`, `_view_category_names(view)`, `_view_vendor_rules(view)`.

Key shared helpers in `app.py`:
- `_style_amounts(df)` — green/red amount Styler + dims rows where `Include` is False.
- `_hbar(data, value, color, title)` — horizontal bar chart.
- `_editable_txn_table(rows, key, cat_options)` — **editable** transactions table (Category dropdown + Include checkbox) that persists edits via `db.set_transaction_category` / `db.set_transaction_included` and reruns. Used on Dashboard and in Analysis drill-down rows.
- `_vendor_manager(view, key_prefix)` — add/edit/delete vendor groups (used in Categories tab AND Analysis expander).
- `_manage_files_section(view, pid)` — imported-files list + untracked cleanup (Import tab).

Analytics engine (`modules/analytics.py`) — **all pure, all route through `_df` (drops `included=0`) → `_split` (refund-netting)**:
- Money: `monthly_savings` (income/spend/savings/**savings_rate**/**complete** month flag), `latest_complete_month`, `category_totals`, `income_by_category`, `spending_by_category_over_time`, `spend_by_parent`, `budget_status` (pro-rated), `month_over_month_change`.
- Advanced: `filter_transactions(txns, *, day_types, dow, date_range, event, categories, people, months)` → **returns a list of txn dicts** (keystone: every other fn works on the filtered subset). `compare`, `drill` (category→vendor→rows), `vendor_of`, `user_overlap`, `per_day_normalize`, `count_matching_days`, `_with_dates`, `event_mask`, `WORKDAYS`/`WEEKENDS`/`DOW_NAMES`.
- Net worth: `net_worth`, `net_worth_trend`, `month_end_balances`.

## 4. What was built/changed THIS session (all verified, tests green)
1. **Audited** the prior agent's W1+W2+tests — correct. Added `pytest` to requirements (was missing).
2. **Advanced analytics + 📈 Analysis tab** (research-designed): Explore (filter bar + Category→**Vendor**→rows drill), Compare (Weekdays vs Weekends, month-over-month, per-day fairness), People (You-vs-Spouse mutual spending). Filter bar: date range, day type, day-of-week, event (Workdays/Weekends), **Months multiselect (non-contiguous)**, categories.
3. **Budgets + parent categories** — DB tables + `set_budget`/`get_budgets`/`category_parents`, `analytics.budget_status` (pro-rated on-track) + `spend_by_parent`. **UI NOT built yet** (engine only).
4. **Vendor groups** — `vendors` table (seeded: Amazon, MTA, NYSC, PATH, Uber, Lyft, Whole Foods, Apple, Verizon, Grubhub, Venmo, Zelle), `vendor_of`, drill groups by vendor. Editable in **Categories tab** and **Analysis** expander (`_vendor_manager`).
5. **Income taxonomy** — `_STARTER_CATEGORIES` seeded per person (Salary/Reimbursement/Rewards + common spend cats) so income isn't one bucket.
6. **Net Worth month-end balances** — transactions now store a `balance` column; `analytics.month_end_balances`; Net Worth tab "Manage" popover can **populate month-end balances from imported bank statements** (`db.transactions_for_file`) or record manual balance points; per-account balance-history chart (`db.account_snapshots`). Generalizes to investments/401k/HSA via manual points.
7. **Dashboard reworked** to month-trend charts: **Spend vs income by month** (line) + **Spending by category by month** (multi-line, category multiselect), a **month-range slider**, drag/scroll **zoom** (temporal x-axis, `tickCount="month"` so one tick per month). KPIs (income/spend/savings/savings-rate/net-worth) and the transactions table kept.
8. **Dashboard transactions table:** editable Category + Include, and a **"View file"** dropdown to filter by imported statement (or Untracked).
9. **Import polish:** Category cell is a dropdown again + a **➕ New category** popover above the (form-batched) table; "just imported this session" shows a friendly message instead of the dedup warning; new categories auto-created on import.
10. **Review/optimize pass:** removed dead `defaultdict` import; replaced all 15 `use_container_width=True` → `width="stretch"` (deprecation gone); removed an unnecessary try/except in vendor seeding. **pyflakes clean.**

## 5. Data model (SQLite, `modules/database.py`)
- `people(id, name)` — seeded You/Spouse.
- `categories(id, person_id, name, keywords, parent)` — `parent` = rollup group (migration-added).
- `transactions(id, person_id, date, description, amount, category, source, file_hash, included, balance)` — `included` 0=excluded; `balance`=running balance (migration-added).
- `imported_files(...)` — dedup by `(person_id, file_hash)`.
- `goals(...)`, `accounts(...)`, `balance_snapshots(account_id, date, balance UNIQUE per day)`.
- `budgets(id, person_id, category, amount)` — person_id NULL = household (manual upsert in `set_budget`).
- `vendors(id, person_id, name, keywords)` — seeded `_STARTER_VENDORS`.

## 6. Remaining backlog (from the merged finance-expert + product review)
Still TODO (engine for budgets/parent exists; UI does not):
- **Budgets UI** — Categories-tab budget inputs + a Dashboard "this month's budgets" card with pace bars (use `analytics.budget_status`).
- **Parent-category UI** — set a category's parent in the Categories tab; optional parent rollup on charts (`analytics.spend_by_parent`).
- **Event tagging (P2 of analytics design)** — `events` + `transaction_tags` tables for user-defined recurring (birthdays, paydays) and one-off windows (a trip, sick days); wire into `filter_transactions(event=…)` + an event picker/manager. (`event_mask` already supports window + recurring rules.)
- **W4:** cash-flow chart variant, **alerts** (surface `month_over_month_change` with a rolling-3-month baseline), **recurring/subscription** detection panel.
- **W1#3 Statement reconciliation** — assert `begin + Σamounts == end` from the running balance and show pass/fail on import (data ties to the penny: bank ends $52,028.66).
- **W5:** confirm **dialogs** (`st.dialog`) on destructive actions (Clear all, delete import/account); **rename-people UI** (`db.rename_person` exists, no UI); transfer-pair matching across the two statements.

## 7. Decisions / gotchas to remember
- **Account model:** kept accounts **decoupled** from transactions (a separate ledger) rather than a risky `account_id` FK refactor — net worth/reconciliation/month-end are delivered via statement balances + manual points. Design doc: `docs/superpowers/specs/2026-06-17-net-worth-design.md`.
- **Refund/transfer correctness:** positives on `credit_card`/`amazon` sources are **refunds** (net against category spend); bank positives are income; detected transfers (credit-card payments) are kept but `included=0` (dimmed, toggleable). Never sum `amount` directly — go through `_split`.
- **Partial months:** statement cycles ≠ calendar months; `monthly_savings` flags `complete`; KPIs use the latest *complete* month and never delta two partial months.
- **Existing data caveat:** the ~150 rows imported before this session have `balance = NULL`, so the Net Worth "populate from statements" needs the bank statement **re-imported** to capture running balances. Same for editable-category niceties — fully effective on new imports.
- **Streamlit limits we worked around:** data-grid cells can't be type-to-search combos (dropdown + "New category" box); drill-down is control-driven (selectboxes) not chart-click; forms batch the import editor.
- **AppTest** doesn't exercise the import flow (no file upload), so verify import/parse changes with an offline parse script against the sample CSVs, plus pytest.

## 8. Suggested next step on resume
1. `git status` to confirm the uncommitted set above is intact; decide with the user whether to commit this session's work.
2. Pick the highest-value remaining item — **Budgets UI** (engine + tests already done) is the biggest user-facing win and low-risk.
3. Keep the loop: edit → `py_compile` → `pytest -q` → AppTest boot (You + Household) → restart headless → confirm health at `/_stcore/health`.
