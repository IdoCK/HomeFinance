# Multi-Currency P1 — Display + Toggle Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Depends on:** P0 (`2026-06-22-multi-currency-p0-ledger-fx.md`) — `transactions.amount_base`, `modules/fx.py`, and the `fx_rates` table must exist.

**Goal:** Add a global `$ USD | ₪ ILS` display toggle that re-expresses every money surface, backed by a `?display=` query param on the money endpoints and a new `/fx` router — defaulting to USD so the common path does zero conversion.

**Architecture:** Money endpoints accept `display: str = "USD"`. Internally they feed analytics the USD `amount_base` (so all math is one currency), then multiply the outputs by today's USD→display factor (`1.0` for USD = no-op, no network). The transactions list converts each row at its own txn-date rate and returns the original alongside. The frontend adds a `CurrencyProvider` (localStorage `hf-currency`, default `USD`), a top-bar pill, and a currency-aware `Money`; pages add `currency` to their fetch `useEffect` deps and refetch converted figures on toggle.

**Tech Stack:** FastAPI + pydantic v2, `modules/fx.py` (P0), React 18 + TypeScript, Vite, vitest + Testing Library, `@tanstack/react-table`.

## Global Constraints

- **Default display = USD.** `display="USD"` ⇒ factor `1.0`, no conversion, no network. Conversion only engages for `display="ILS"`.
- **Pivot = USD** (from P0). Analytics always operate on `amount_base` (USD); display conversion happens only at the response boundary.
- **Rate dates (design §2.3):** "current" aggregates (overview totals, budgets, net worth, recurring, goals) convert at **today's** rate; the **transactions list** converts each row at **its own txn-date** rate.
- **Offline-safe:** if a needed rate is unavailable, return the USD figure and flag (`rate_stale`/`display_unavailable`) — never a wrong/zero number, never a 500.
- **Data-minimization (P0 invariant) still holds** — the only network path remains `fx.fetch_rate`.
- **No FX math in the client.** The frontend only chooses which currency to render and surfaces originals; all conversion is server-side.
- Python tests: `venv/Scripts/python -m pytest <path> -v`. Web tests: `cd web && npm run test` (vitest run).

---

### Task 1: `fx.display_factor` + `fx.base_txns` boundary helpers

**Files:**
- Modify: `modules/fx.py`
- Test: `tests/test_fx_display.py` (create)

**Interfaces:**
- Produces:
  - `display_factor(display: str, on_date: str | None = None) -> float | None` — USD→`display` rate for `on_date` (today if None). `1.0` for USD (no lookup/network). `None` if unavailable.
  - `base_txns(txns: list[dict]) -> list[dict]` — shallow copies with `amount` replaced by `amount_base` (falls back to `amount` when base is None), so analytics sum USD.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fx_display.py
from modules import database, fx


def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "t.db")
    database.init_db()


def test_usd_factor_is_one_no_network(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    monkeypatch.setattr(fx, "_http_get_json",
                        lambda url: (_ for _ in ()).throw(AssertionError("no network for USD")))
    assert fx.display_factor("USD") == 1.0


def test_ils_factor_uses_today_rate(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    from datetime import date
    fx.upsert_rate(date.today().isoformat(), "USD", "ILS", 3.7)
    assert fx.display_factor("ILS") == 3.7


def test_base_txns_swaps_amount_to_base(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    rows = [{"amount": 400.0, "amount_base": 100.0, "currency": "ILS"},
            {"amount": 50.0, "amount_base": None, "currency": "USD"}]
    out = fx.base_txns(rows)
    assert out[0]["amount"] == 100.0      # uses base
    assert out[1]["amount"] == 50.0       # falls back to amount
    assert rows[0]["amount"] == 400.0     # original not mutated
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python -m pytest tests/test_fx_display.py -v`
Expected: FAIL — `module 'modules.fx' has no attribute 'display_factor'`.

- [ ] **Step 3: Add the helpers to `modules/fx.py`**

```python
def display_factor(display, on_date=None):
    """USD -> display multiplier for `on_date` (today if None). 1.0 for USD with
    no lookup/network. None if the rate is unavailable (offline + uncached)."""
    if display == PIVOT:
        return 1.0
    on = on_date or _date.today().isoformat()
    return _rate_or_fetch(on, PIVOT, display)


def base_txns(txns):
    """Copies with `amount` set to the USD base, so analytics sum one currency."""
    out = []
    for t in txns:
        base = t.get("amount_base")
        out.append({**t, "amount": base if base is not None else t.get("amount")})
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python -m pytest tests/test_fx_display.py -v`
Expected: PASS (all 3).

- [ ] **Step 5: Commit**

```bash
git add modules/fx.py tests/test_fx_display.py
git commit -m "feat(fx): display_factor + base_txns boundary helpers"
```

---

### Task 2: Transactions endpoint — `display` param + per-row txn-date conversion

**Files:**
- Modify: `backend/api/transactions.py:12-15` (`list_transactions`)
- Test: `tests/api/test_transactions_display.py` (create)

**Interfaces:**
- Consumes: `fx.convert`, `db.get_transactions`.
- Produces: `GET /transactions?display=ILS|USD`. Each row keeps `amount_base` (USD) and adds `original_amount` (= the stored `amount`), `original_currency` (= `currency`), `display_amount` (converted at the row's txn date), and `rate_stale` (bool). `amount` is overwritten with `display_amount` so existing consumers render the display value. USD default ⇒ `display_amount == amount_base`.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_transactions_display.py
def _commit(client, monkeypatch, rows):
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": 4.0}})
    pid = client.get("/api/people").json()[0]["id"]
    client.post("/api/import/commit", json={
        "person_id": pid, "filename": "f.csv", "file_hash": "h", "source": "bank", "rows": rows})
    return pid


def test_default_display_is_usd_passthrough(client, monkeypatch):
    pid = _commit(client, monkeypatch, [
        {"date": "2026-03-13", "description": "PAY", "amount": 1000.0, "currency": "USD"}])
    row = client.get("/api/transactions", params={"person_id": pid}).json()[0]
    assert row["original_amount"] == 1000.0
    assert row["original_currency"] == "USD"
    assert row["amount"] == 1000.0          # display == base for USD
    assert row["rate_stale"] is False


def test_ils_display_converts_each_row_at_its_date(client, monkeypatch):
    from modules import fx
    pid = _commit(client, monkeypatch, [
        {"date": "2026-03-13", "description": "PAY", "amount": 1000.0, "currency": "USD"}])
    # 1 USD = 3.5 ILS today-of-row
    fx.upsert_rate("2026-03-13", "USD", "ILS", 3.5)
    row = client.get("/api/transactions", params={"person_id": pid, "display": "ILS"}).json()[0]
    assert row["original_amount"] == 1000.0 and row["original_currency"] == "USD"
    assert row["amount"] == 3500.0          # 1000 USD * 3.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python -m pytest tests/api/test_transactions_display.py -v`
Expected: FAIL — response rows have no `original_amount` / `amount` unchanged.

- [ ] **Step 3: Rewrite `list_transactions`** (`backend/api/transactions.py`)

```python
from modules import fx

@router.get("")
def list_transactions(person_id: Optional[int] = None, display: str = "USD"):
    """person_id omitted -> all people (Joint). `display` re-expresses each row at
    its own transaction-date rate; the original amount+currency are preserved."""
    rows = db.get_transactions(person_id)
    for t in rows:
        base = t.get("amount_base")
        base = t.get("amount") if base is None else base
        conv = fx.convert(base, display, t.get("date"))
        t["original_amount"] = t.get("amount")
        t["original_currency"] = t.get("currency", "USD")
        t["amount_base"] = base
        t["rate_stale"] = conv is None
        t["amount"] = base if conv is None else conv   # never show a wrong/zero number
    return rows
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python -m pytest tests/api/test_transactions_display.py -v`
Expected: PASS (both).

- [ ] **Step 5: Regression**

Run: `venv/Scripts/python -m pytest tests/api/test_transactions.py -q`
Expected: PASS (default display=USD leaves `amount` equal to the legacy value).

- [ ] **Step 6: Commit**

```bash
git add backend/api/transactions.py tests/api/test_transactions_display.py
git commit -m "feat(api): transactions display param + per-row txn-date conversion"
```

---

### Task 3: Overview endpoint — `display` param (today-rate aggregates)

**Files:**
- Modify: `backend/api/overview.py:18-70` (`overview`)
- Test: `tests/api/test_overview_display.py` (create)

**Interfaces:**
- Consumes: `fx.display_factor`, `fx.base_txns`.
- Produces: `GET /overview?display=ILS|USD`. Analytics run on USD base; every money scalar (`income`, `spend`, `net`, `by_category` values, `series[].income/spend/net`, `split[].spend`, `alerts[].current/baseline/delta`) is multiplied by today's factor. `savings_rate`, `pct`, `month`, `complete` are ratios/labels — unchanged. USD ⇒ factor 1.0 (no change).

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_overview_display.py
from datetime import date


def _seed(client, monkeypatch):
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": 4.0}})
    pid = client.get("/api/people").json()[0]["id"]
    m = date.today().strftime("%Y-%m")
    client.post("/api/import/commit", json={
        "person_id": pid, "filename": "f.csv", "file_hash": "h", "source": "bank",
        "rows": [
            {"date": f"{m}-05", "description": "PAY", "amount": 2000.0, "currency": "USD"},
            {"date": f"{m}-06", "description": "STORE", "amount": -500.0, "currency": "USD"},
        ]})
    return pid


def test_overview_usd_unchanged(client, monkeypatch):
    pid = _seed(client, monkeypatch)
    o = client.get("/api/overview", params={"person_id": pid}).json()
    assert o["income"] == 2000.0 and o["spend"] == 500.0


def test_overview_ils_scales_by_today_factor(client, monkeypatch):
    from modules import fx
    pid = _seed(client, monkeypatch)
    fx.upsert_rate(date.today().isoformat(), "USD", "ILS", 3.0)
    o = client.get("/api/overview", params={"person_id": pid, "display": "ILS"}).json()
    assert o["income"] == 6000.0 and o["spend"] == 1500.0   # x3
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python -m pytest tests/api/test_overview_display.py -v`
Expected: FAIL on the ILS case (income still 2000).

- [ ] **Step 3: Add base + factor to `overview`** (`backend/api/overview.py`)

Add the import and a small scaler, swap `txns` to base, and scale the response. Concretely:

```python
from modules import fx

def _scale(v, f):
    return v if v is None else round(v * f, 2)

@router.get("")
def overview(person_id: Optional[int] = None, month: Optional[str] = None, display: str = "USD"):
    txns = fx.base_txns(db.get_transactions(person_id))   # analytics in USD
    f = fx.display_factor(display) or 1.0                  # offline fallback: USD
    sav = analytics.monthly_savings(txns)
    if sav.empty:
        return _empty()
    # ... (recs/months/month/series/split build UNCHANGED, operating on USD) ...
```

Then at the `return {...}` (lines 58-70), wrap each money field with `_scale(..., f)` and scale the nested structures before returning:

```python
    by_category = {k: _scale(v, f) for k, v in analytics.category_totals(month_txns).items()}
    series = [{**p, "income": _scale(p["income"], f), "spend": _scale(p["spend"], f),
               "net": _scale(p["net"], f)} for p in series]
    if split is not None:
        split = [{**s, "spend": _scale(s["spend"], f)} for s in split]
    alerts = [{**a, "current": _scale(a["current"], f), "baseline": _scale(a["baseline"], f),
               "delta": _scale(a["delta"], f)} for a in analytics.spending_alerts(txns)]
    return {
        "month": month, "months": months,
        "income": _scale(sel["income"], f), "spend": _scale(sel["spend"], f),
        "net": _scale(sel["net"], f), "savings_rate": sel["savings_rate"],
        "complete": sel["complete"], "by_category": by_category,
        "alerts": alerts, "series": series, "split": split,
    }
```

(Keep the existing `series` and `split` construction above this block; the lines here re-map them through `_scale`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python -m pytest tests/api/test_overview_display.py -v`
Expected: PASS (both).

- [ ] **Step 5: Regression**

Run: `venv/Scripts/python -m pytest tests/api/test_overview.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/api/overview.py tests/api/test_overview_display.py
git commit -m "feat(api): overview display param (today-rate scaling)"
```

---

### Task 4: NetWorth & Budgets endpoints — `display` param

**Files:**
- Modify: `backend/api/networth.py:17-43` (`get_networth`, `reconcile`), `backend/api/budgets.py:12-18` (`list_budgets`)
- Test: `tests/api/test_networth_budgets_display.py` (create)

**Interfaces:**
- Consumes: `fx.display_factor`, `fx.base_txns`, `fx.to_base`.
- Produces:
  - `GET /networth?display=` — account balances are converted to USD base via each account's own `currency` at today's rate, summed in USD, then scaled to display. Each returned account gains `original_balance` + `currency`; `balance` becomes the display value. `reconcile` stays in **native** currency (design §3.4) and is unchanged.
  - `GET /budgets?display=` — `spent`/`budget`/`expected_to_date`/`projected_eom` scaled by today's factor; `pct`/`status` unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_networth_budgets_display.py
from datetime import date


def test_networth_scales_balances(client, monkeypatch):
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": 4.0}})
    pid = client.get("/api/people").json()[0]["id"]
    client.post("/api/networth/accounts", json={
        "person_id": pid, "name": "Checking", "kind": "checking", "is_asset": True, "balance": 1000.0})
    fx.upsert_rate(date.today().isoformat(), "USD", "ILS", 3.0)

    usd = client.get("/api/networth", params={"person_id": pid}).json()
    assert usd["summary"]["assets"] == 1000.0
    ils = client.get("/api/networth", params={"person_id": pid, "display": "ILS"}).json()
    assert ils["summary"]["assets"] == 3000.0
    assert ils["accounts"][0]["original_balance"] == 1000.0


def test_budgets_scale(client, monkeypatch):
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": 4.0}})
    pid = client.get("/api/people").json()[0]["id"]
    m = date.today().strftime("%Y-%m")
    client.post("/api/import/commit", json={
        "person_id": pid, "filename": "f.csv", "file_hash": "h", "source": "bank",
        "rows": [{"date": f"{m}-05", "description": "STORE", "amount": -200.0,
                  "currency": "USD", "category": "Shopping"}]})
    client.put("/api/budgets", json={"person_id": pid, "category": "Shopping", "amount": 500.0})
    fx.upsert_rate(date.today().isoformat(), "USD", "ILS", 2.0)
    b = client.get("/api/budgets", params={"person_id": pid, "display": "ILS"}).json()
    row = next(r for r in b if r["category"] == "Shopping")
    assert row["spent"] == 400.0 and row["budget"] == 1000.0   # x2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python -m pytest tests/api/test_networth_budgets_display.py -v`
Expected: FAIL — ILS values not scaled / `original_balance` missing.

- [ ] **Step 3a: NetWorth** (`backend/api/networth.py`)

```python
from datetime import date as _date
from modules import fx

def _accounts_to_base(accounts):
    """Copies with balance converted to USD via each account's own currency
    (current balances -> today's rate). Adds original_balance + currency."""
    today = _date.today().isoformat()
    out = []
    for a in accounts:
        ccy = a.get("currency", "USD")
        base = a["balance"] if ccy == "USD" else (fx.to_base(a["balance"], ccy, today) or a["balance"])
        out.append({**a, "balance": base, "original_balance": a["balance"], "currency": ccy})
    return out
```

In `get_networth`, after `accounts = db.list_accounts(scope)`:

```python
    accounts = _accounts_to_base(db.list_accounts(scope))
    f = fx.display_factor(display) or 1.0
    summary = analytics.net_worth(accounts)               # USD
    summary = {k: round(v * f, 2) for k, v in summary.items()}
    trend_df = analytics.net_worth_trend(db.get_snapshots(scope))
    trend = [] if trend_df.empty else trend_df.to_dict(orient="records")
    trend = [{**p, "assets": round(p["assets"] * f, 2), "liabilities": round(p["liabilities"] * f, 2),
              "net": round(p["net"] * f, 2)} for p in trend]
    delta = round(summary["net"] - trend[-2]["net"], 2) if len(trend) >= 2 else None
    # accounts shown in display currency, originals preserved
    disp_accounts = [{**a, "balance": round(a["balance"] * f, 2)} for a in accounts]
```

Update the signature to `def get_networth(person_id: Optional[int] = None, display: str = "USD"):`, scale each `split` entry's `net/assets/liabilities` by `f`, and return `"accounts": disp_accounts`. (`reconcile` is left untouched — native currency by design.)

- [ ] **Step 3b: Budgets** (`backend/api/budgets.py`)

```python
from modules import fx

@router.get("")
def list_budgets(person_id: Optional[int] = None, display: str = "USD"):
    txns = fx.base_txns(db.get_transactions(person_id))
    budgets = db.get_budgets(person_id)
    parents = db.category_parents(person_id) if person_id is not None else {}
    rows = analytics.budget_status(txns, budgets, parents)
    f = fx.display_factor(display) or 1.0
    if f == 1.0:
        return rows
    money = ("spent", "budget", "amount", "expected_to_date", "projected_eom")
    return [{**r, **{k: round(r[k] * f, 2) for k in money if k in r and r[k] is not None}} for r in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python -m pytest tests/api/test_networth_budgets_display.py -v`
Expected: PASS (both).

- [ ] **Step 5: Regression**

Run: `venv/Scripts/python -m pytest tests/api/test_networth_api.py tests/api/test_budgets.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/api/networth.py backend/api/budgets.py tests/api/test_networth_budgets_display.py
git commit -m "feat(api): networth + budgets display param"
```

---

### Task 5: Recurring & Goals endpoints — `display` param

**Files:**
- Modify: `backend/api/recurring.py` (`get_recurring`), `backend/api/goals.py` (`list_goals`)
- Test: `tests/api/test_recurring_goals_display.py` (create)

**Interfaces:**
- Consumes: `fx.base_txns` (recurring runs on txns), `fx.display_factor`.
- Produces: `GET /recurring?display=` scales `committed.fixed/variable/total` and each charge's `typical_amount`/`prior_typical`/`last_amount`/`monthly_cost`/`annual_cost`; `confidence`/`cadence` unchanged. `GET /goals?display=` scales `target_amount`/`saved_amount`/`monthly_needed`; `percent` unchanged.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_recurring_goals_display.py
from datetime import date


def test_goals_scale(client, monkeypatch):
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": 4.0}})
    pid = client.get("/api/people").json()[0]["id"]
    client.post("/api/goals", json={"person_id": pid, "name": "Car", "target_amount": 10000.0})
    fx.upsert_rate(date.today().isoformat(), "USD", "ILS", 3.0)
    g = client.get("/api/goals", params={"person_id": pid, "display": "ILS"}).json()
    car = next(x for x in g if x["name"] == "Car")
    assert car["target_amount"] == 30000.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python -m pytest tests/api/test_recurring_goals_display.py -v`
Expected: FAIL — target still 10000.

- [ ] **Step 3a: Goals** (`backend/api/goals.py` — add `display` to the GET and scale)

```python
from modules import fx
# in the list endpoint signature: def list_goals(person_id: Optional[int] = None, display: str = "USD"):
# after building the response list `out`:
    f = fx.display_factor(display) or 1.0
    if f != 1.0:
        keys = ("target_amount", "saved_amount", "monthly_needed")
        out = [{**g, **{k: (None if g.get(k) is None else round(g[k] * f, 2)) for k in keys}} for g in out]
    return out
```

- [ ] **Step 3b: Recurring** (`backend/api/recurring.py`)

```python
from modules import fx
# signature: def get_recurring(person_id: Optional[int] = None, display: str = "USD"):
# feed analytics USD base:
    data = analytics.recurring_charges(fx.base_txns(db.get_transactions(person_id)))
    f = fx.display_factor(display) or 1.0
    if f != 1.0:
        ck = ("typical_amount", "prior_typical", "last_amount", "monthly_cost", "annual_cost")
        data["charges"] = [{**c, **{k: round(c[k] * f, 2) for k in ck if c.get(k) is not None}}
                           for c in data["charges"]]
        data["committed"] = {k: round(v * f, 2) for k, v in data["committed"].items()}
    return data
```

(If `recurring.py` currently passes `db.get_transactions(...)` straight to analytics, swap that single call to `fx.base_txns(db.get_transactions(...))` as shown.)

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python -m pytest tests/api/test_recurring_goals_display.py -v`
Expected: PASS.

- [ ] **Step 5: Regression**

Run: `venv/Scripts/python -m pytest tests/api/test_recurring.py tests/api/test_goals.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/api/recurring.py backend/api/goals.py tests/api/test_recurring_goals_display.py
git commit -m "feat(api): recurring + goals display param"
```

---

### Task 6: `/fx` router — inspect, manual upsert, opt-in refresh

**Files:**
- Create: `backend/api/fx.py`
- Modify: `backend/main.py:10` (import), `:45` (include_router)
- Test: `tests/api/test_fx_router.py` (create)

**Interfaces:**
- Consumes: `modules.fx`, `modules.database`.
- Produces:
  - `GET /fx/rates` → `{ "source": str|None, "last_fetched": str|None, "count": int, "rates": [{rate_date, base, quote, rate, source}] }` (read-only inspect).
  - `PUT /fx/rates` (`FxRateUpsert`) → manual rate entry (`source='manual'`).
  - `POST /fx/refresh` (`FxRefresh{ dates: list[str], base="USD", quote="ILS" }`) → explicit, user-initiated fetch for the given dates; returns `{ fetched: int, failed: int }`.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_fx_router.py
def test_manual_upsert_and_inspect(client):
    client.put("/api/fx/rates", json={"rate_date": "2026-03-13", "base": "USD",
                                       "quote": "ILS", "rate": 3.6})
    data = client.get("/api/fx/rates").json()
    assert data["count"] == 1
    assert data["rates"][0]["rate"] == 3.6
    assert data["rates"][0]["source"] == "manual"


def test_refresh_fetches_listed_dates(client, monkeypatch):
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": 3.9}})
    out = client.post("/api/fx/refresh", json={"dates": ["2026-03-13", "2026-03-14"]}).json()
    assert out["fetched"] == 2 and out["failed"] == 0
    assert client.get("/api/fx/rates").json()["count"] == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python -m pytest tests/api/test_fx_router.py -v`
Expected: FAIL — `404` (router not mounted).

- [ ] **Step 3a: Schemas** (`backend/schemas.py`)

```python
class FxRateUpsert(BaseModel):
    rate_date: str
    base: str = "USD"
    quote: str = "ILS"
    rate: float


class FxRefresh(BaseModel):
    dates: list[str]
    base: str = "USD"
    quote: str = "ILS"
```

- [ ] **Step 3b: Router** (`backend/api/fx.py`)

```python
from fastapi import APIRouter

from modules import database as db
from modules import fx as fxmod
from backend.schemas import FxRateUpsert, FxRefresh

router = APIRouter(prefix="/fx", tags=["fx"])


@router.get("/rates")
def list_rates():
    with db.get_conn() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT rate_date, base, quote, rate, source, fetched_at "
            "FROM fx_rates ORDER BY rate_date DESC")]
    last = next((r["fetched_at"] for r in rows if r["fetched_at"]), None)
    src = rows[0]["source"] if rows else None
    return {"source": src, "last_fetched": last, "count": len(rows), "rates": rows}


@router.put("/rates")
def upsert_rate(body: FxRateUpsert):
    fxmod.upsert_rate(body.rate_date, body.base, body.quote, body.rate, source="manual")
    return {"ok": True}


@router.post("/refresh")
def refresh(body: FxRefresh):
    """Explicit, user-initiated fetch. Sends only date+currency pair per date."""
    fetched = failed = 0
    for d in body.dates:
        if fxmod.fetch_rate(d, body.base, body.quote) is not None:
            fetched += 1
        else:
            failed += 1
    return {"fetched": fetched, "failed": failed}
```

- [ ] **Step 3c: Mount it** (`backend/main.py`)

Add `fx` to the import list on line 10 (`from backend.api import budgets, ..., fx`) and add after line 45:

```python
    app.include_router(fx.router, prefix="/api")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python -m pytest tests/api/test_fx_router.py -v`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add backend/api/fx.py backend/schemas.py backend/main.py tests/api/test_fx_router.py
git commit -m "feat(api): /fx router — inspect, manual upsert, opt-in refresh"
```

---

### Task 7: `CurrencyProvider` — `web/src/lib/currency.tsx`

**Files:**
- Create: `web/src/lib/currency.tsx`
- Test: `web/src/lib/currency.test.tsx` (create)

**Interfaces:**
- Produces: `CurrencyProvider`, `useCurrency()` → `{ currency: "USD"|"ILS"; setCurrency; symbol: string; format: (n, opts?) => string }`. Persists `localStorage["hf-currency"]`, default `"USD"`, sets `document.documentElement.dataset.currency`.

- [ ] **Step 1: Write the failing test**

```tsx
// web/src/lib/currency.test.tsx
import { render, screen, act } from "@testing-library/react";
import { expect, test, beforeEach } from "vitest";
import { CurrencyProvider, useCurrency } from "./currency";

function Probe() {
  const { currency, symbol, setCurrency, format } = useCurrency();
  return (
    <div>
      <span data-testid="cur">{currency}</span>
      <span data-testid="sym">{symbol}</span>
      <span data-testid="fmt">{format(1234.5)}</span>
      <button onClick={() => setCurrency("ILS")}>ils</button>
    </div>
  );
}

beforeEach(() => localStorage.clear());

test("defaults to USD and formats with $", () => {
  render(<CurrencyProvider><Probe /></CurrencyProvider>);
  expect(screen.getByTestId("cur").textContent).toBe("USD");
  expect(screen.getByTestId("sym").textContent).toBe("$");
  expect(screen.getByTestId("fmt").textContent).toBe("$1,234.50");
});

test("switching to ILS persists and reformats", () => {
  render(<CurrencyProvider><Probe /></CurrencyProvider>);
  act(() => screen.getByText("ils").click());
  expect(screen.getByTestId("cur").textContent).toBe("ILS");
  expect(localStorage.getItem("hf-currency")).toBe("ILS");
  expect(screen.getByTestId("fmt").textContent).toContain("₪");
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm run test -- currency`
Expected: FAIL — cannot resolve `./currency`.

- [ ] **Step 3: Write the provider** (`web/src/lib/currency.tsx`)

```tsx
import { createContext, useContext, useEffect, useMemo, useState } from "react";

export type Currency = "USD" | "ILS";
const SYMBOL: Record<Currency, string> = { USD: "$", ILS: "₪" };

type Ctx = {
  currency: Currency;
  setCurrency: (c: Currency) => void;
  symbol: string;
  format: (n: number, opts?: { cents?: boolean; signed?: boolean }) => string;
};
const CurrencyCtx = createContext<Ctx | null>(null);

export function CurrencyProvider({ children }: { children: React.ReactNode }) {
  const [currency, setCurrency] = useState<Currency>(
    () => (localStorage.getItem("hf-currency") as Currency) || "USD",
  );
  useEffect(() => {
    localStorage.setItem("hf-currency", currency);
    document.documentElement.dataset.currency = currency;
  }, [currency]);

  const value = useMemo<Ctx>(() => {
    const fmt = (cents: boolean) =>
      new Intl.NumberFormat("en-US", {
        style: "currency", currency,
        minimumFractionDigits: cents ? 2 : 0, maximumFractionDigits: cents ? 2 : 0,
      });
    return {
      currency, setCurrency, symbol: SYMBOL[currency],
      format: (n, opts) => {
        const s = fmt(opts?.cents ?? true).format(n);
        return opts?.signed && n > 0 ? `+${s}` : s;
      },
    };
  }, [currency]);

  return <CurrencyCtx.Provider value={value}>{children}</CurrencyCtx.Provider>;
}

export function useCurrency() {
  const v = useContext(CurrencyCtx);
  if (!v) throw new Error("useCurrency must be used within <CurrencyProvider>");
  return v;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm run test -- currency`
Expected: PASS (both).

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/currency.tsx web/src/lib/currency.test.tsx
git commit -m "feat(web): CurrencyProvider (default USD, localStorage)"
```

---

### Task 8: Currency-aware `Money` + updated tests

**Files:**
- Modify: `web/src/components/money.tsx`
- Modify: `web/src/components/money.test.tsx`

**Interfaces:**
- Consumes: `useCurrency` (Task 7).
- Produces: `formatMoney(n, currency?: Currency)` (defaults USD — backward compatible). `Money` now reads `useCurrency()` to pick the symbol; new optional props `cents?: boolean` and `original?: { amount: number; currency: Currency }` (renders a muted marker + tooltip when the original currency differs). Existing `value`/`colored`/`accent` unchanged.

- [ ] **Step 1: Update the test first** (`web/src/components/money.test.tsx`)

```tsx
import { render, screen } from "@testing-library/react";
import { expect, test } from "vitest";
import { Money, formatMoney } from "./money";
import { CurrencyProvider } from "@/lib/currency";

const wrap = (ui: React.ReactNode) => render(<CurrencyProvider>{ui}</CurrencyProvider>);

test("formatMoney formats USD by default", () => {
  expect(formatMoney(1234.5)).toBe("$1,234.50");
  expect(formatMoney(-99)).toBe("-$99.00");
});

test("formatMoney formats ILS when asked", () => {
  expect(formatMoney(1234.5, "ILS")).toContain("₪");
});

test("Money colors negatives (USD default)", () => {
  wrap(<Money value={-10} colored />);
  expect(screen.getByText("-$10.00")).toHaveStyle({ color: "var(--neg)" });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm run test -- money`
Expected: FAIL — `formatMoney` takes no currency arg / import error.

- [ ] **Step 3: Rewrite `money.tsx`**

```tsx
import { useCurrency, type Currency } from "@/lib/currency";

const FMT_CACHE: Partial<Record<string, Intl.NumberFormat>> = {};
function fmt(currency: Currency, cents: boolean): Intl.NumberFormat {
  const key = `${currency}-${cents}`;
  return (FMT_CACHE[key] ??= new Intl.NumberFormat("en-US", {
    style: "currency", currency,
    minimumFractionDigits: cents ? 2 : 0, maximumFractionDigits: cents ? 2 : 0,
  }));
}

export function formatMoney(n: number, currency: Currency = "USD"): string {
  return fmt(currency, true).format(n);
}

/** Ledger figure. `colored` tints by sign; `accent` uses the persona color.
 *  Renders in the active display currency (via CurrencyProvider). `original`
 *  surfaces an entered-in-another-currency marker. Tabular-nums for alignment. */
export function Money({
  value, colored = false, accent = false, cents = true,
  original,
}: {
  value: number; colored?: boolean; accent?: boolean; cents?: boolean;
  original?: { amount: number; currency: Currency };
}) {
  const { currency } = useCurrency();
  const color = accent
    ? "var(--persona-solid)"
    : !colored ? undefined
      : value > 0 ? "var(--pos)" : value < 0 ? "var(--neg)" : undefined;
  const showOriginal = original && original.currency !== currency;
  return (
    <span style={{ fontVariantNumeric: "tabular-nums", color }}>
      {fmt(currency, cents).format(value)}
      {showOriginal && (
        <span
          title={`Originally ${formatMoney(original!.amount, original!.currency)}`}
          style={{ color: "var(--fl-muted)", fontSize: "0.82em", marginLeft: 4 }}
        >
          ≈
        </span>
      )}
    </span>
  );
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm run test -- money`
Expected: PASS (all 3).

- [ ] **Step 5: Commit**

```bash
git add web/src/components/money.tsx web/src/components/money.test.tsx
git commit -m "feat(web): currency-aware Money + formatMoney(currency)"
```

---

### Task 9: Wrap `CurrencyProvider` + add the top-bar currency pill

**Files:**
- Modify: `web/src/App.tsx`
- Modify: `web/src/components/app-sidebar.tsx`

**Interfaces:**
- Consumes: `CurrencyProvider`, `useCurrency`.
- Produces: app-wide currency context; a `$ USD | ₪ ILS` segmented pill in the sidebar (modeled on the persona switch), USD listed first/active by default.

- [ ] **Step 1: Wrap the provider** (`web/src/App.tsx`)

```tsx
import { RouterProvider } from "react-router-dom";
import { PersonaProvider } from "@/lib/persona";
import { ThemeProvider } from "@/lib/theme";
import { CurrencyProvider } from "@/lib/currency";
import { router } from "@/routes";

export default function App() {
  return (
    <ThemeProvider>
      <PersonaProvider>
        <CurrencyProvider>
          <RouterProvider router={router} />
        </CurrencyProvider>
      </PersonaProvider>
    </ThemeProvider>
  );
}
```

- [ ] **Step 2: Add the pill** (`web/src/components/app-sidebar.tsx`)

Add the import at the top:

```tsx
import { useCurrency, type Currency } from "@/lib/currency";
```

Inside `AppSidebar`, after `const { theme, toggle } = useTheme();` add:

```tsx
  const { currency, setCurrency } = useCurrency();
  const CURRENCIES: { key: Currency; label: string }[] = [
    { key: "USD", label: "$ USD" },
    { key: "ILS", label: "₪ ILS" },
  ];
```

Then, immediately after the persona segmented switch `</div>` (line ~72), insert a sibling segmented switch:

```tsx
      {/* Display-currency segmented switch (sibling of the persona switch) */}
      <div role="tablist" aria-label="Display currency" style={{ display: "flex", gap: 4, background: "#EEF0F3", borderRadius: 14, padding: 4, margin: "0 2px 16px" }}>
        {CURRENCIES.map((c) => {
          const active = currency === c.key;
          return (
            <button
              key={c.key} role="tab" aria-selected={active} onClick={() => setCurrency(c.key)}
              style={{
                flex: 1, fontSize: 11.5, fontWeight: 600, padding: "7px 0", borderRadius: 10,
                border: "none", cursor: "pointer",
                background: active ? "#fff" : "transparent",
                color: active ? "var(--fl-ink)" : "var(--fl-muted)",
                boxShadow: active ? "0 2px 8px -2px rgba(22,24,29,.18)" : "none",
              }}
            >
              {c.label}
            </button>
          );
        })}
      </div>
```

- [ ] **Step 3: Verify the app builds + existing tests pass**

Run: `cd web && npm run test -- app-sidebar` (if a sidebar test exists) then `npm run build`
Expected: build succeeds; the sidebar shows the currency pill below the persona switch.

- [ ] **Step 4: Commit**

```bash
git add web/src/App.tsx web/src/components/app-sidebar.tsx
git commit -m "feat(web): wrap CurrencyProvider + top-bar currency pill"
```

---

### Task 10: `api.ts` — display plumbing + Transaction type

**Files:**
- Modify: `web/src/lib/api.ts`
- Test: `web/src/lib/api.test.ts` (extend)

**Interfaces:**
- Consumes: `Currency` from `currency.tsx`.
- Produces: every money getter gains an optional `display?: Currency` passed as the `display` query param; `Transaction` gains `original_amount: number`, `original_currency: Currency`, `amount_base: number`, `rate_stale: boolean`; `Account` gains `original_balance?: number`, `currency?: string`.

- [ ] **Step 1: Write/extend the failing test** (`web/src/lib/api.test.ts`)

Add a case asserting the query string includes `display`:

```ts
import { expect, test, vi } from "vitest";
import { getTransactions } from "./api";

test("getTransactions forwards display param", async () => {
  const spy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response("[]", { status: 200 }));
  await getTransactions({ personId: 1, display: "ILS" });
  expect(String(spy.mock.calls[0][0])).toContain("display=ILS");
  spy.mockRestore();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm run test -- api`
Expected: FAIL — `getTransactions` ignores `display` (no `display=ILS` in URL).

- [ ] **Step 3: Edit `api.ts`**

Add the import and extend the types + getters. Representative edits:

```ts
import type { Currency } from "@/lib/currency";

// Transaction type:
export type Transaction = {
  id: number; person_id: number; date: string; description: string;
  amount: number; category: string; source: string; included: number;
  balance: number | null; person: string;
  original_amount: number; original_currency: Currency; amount_base: number; rate_stale: boolean;
};

export const getTransactions = (p: { personId?: number; display?: Currency }) =>
  apiGet<Transaction[]>("/transactions", { person_id: p.personId, display: p.display });

export const getOverview = (p: { personId?: number; month?: string; display?: Currency }) =>
  apiGet<Overview>("/overview", { person_id: p.personId, month: p.month, display: p.display });

export const getBudgets = (p: { personId?: number; display?: Currency }) =>
  apiGet<Budget[]>("/budgets", { person_id: p.personId, display: p.display });

export const getRecurring = (p: { personId?: number; display?: Currency }) =>
  apiGet<RecurringData>("/recurring", { person_id: p.personId, display: p.display });

export const getGoals = (p: { personId?: number; display?: Currency }) =>
  apiGet<Goal[]>("/goals", { person_id: p.personId, display: p.display });

export const getNetWorth = (p: { personId?: number; display?: Currency }) =>
  apiGet<NetWorthData>("/networth", { person_id: p.personId, display: p.display });
```

Also extend `Account` with `original_balance?: number; currency?: string;`. (`qs()` already drops `undefined`, so omitting `display` keeps the USD default.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm run test -- api`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/lib/api.ts web/src/lib/api.test.ts
git commit -m "feat(web): thread display param + extend Transaction/Account types"
```

---

### Task 11: Pages refetch on currency change + Transactions "Original" column

**Files:**
- Modify: `web/src/pages/Transactions.tsx`, `Overview.tsx`, `Budgets.tsx`, `NetWorth.tsx`, `Recurring.tsx`, `Goals.tsx`
- Test: `web/src/pages/Transactions.test.tsx` (extend)

**Interfaces:**
- Consumes: `useCurrency`, the `display`-aware getters (Task 10), currency-aware `Money` (Task 8).
- Produces: each page reads `const { currency } = useCurrency();`, passes `display: currency` to its getter, and adds `currency` to the data `useEffect` dependency array so it refetches on toggle. Transactions gains an **Original** column.

- [ ] **Step 1: Extend the Transactions test**

```tsx
// add to web/src/pages/Transactions.test.tsx — render within CurrencyProvider and
// assert an Original column header exists. (Wrap the existing render helper with
// <CurrencyProvider> if it isn't already.)
import { CurrencyProvider } from "@/lib/currency";
// ...
test("shows an Original column header", async () => {
  // ...render Transactions inside <CurrencyProvider> with a mocked getTransactions
  // returning a row with original_currency !== "USD"...
  expect(await screen.findByText(/Original/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm run test -- Transactions`
Expected: FAIL — no "Original" header.

- [ ] **Step 3a: Transactions page** (`web/src/pages/Transactions.tsx`)

Add `import { useCurrency } from "@/lib/currency";`, then in the component:

```tsx
  const { currency } = useCurrency();
```

Change the data effect to depend on currency and pass display:

```tsx
  useEffect(() => {
    let alive = true;
    getTransactions({ personId, display: currency }).then((d) => alive && setData(d)).catch(() => alive && setData([]));
    getTransferPairs(personId).then((p) => alive && setPairs(p)).catch(() => alive && setPairs([]));
    return () => { alive = false; };
  }, [personId, currency]);
```

Add an Original column right after the `amount` column in the `columns` memo:

```tsx
      {
        id: "original",
        header: "Original",
        enableSorting: false,
        cell: (c) => {
          const t = c.row.original;
          if (t.original_currency === currency) return <span style={{ color: "var(--fl-muted)" }}>—</span>;
          return (
            <span style={{ color: "var(--fl-muted)", fontSize: 12, fontVariantNumeric: "tabular-nums" }}>
              {formatMoney(t.original_amount, t.original_currency)}
            </span>
          );
        },
      },
```

Import `formatMoney` alongside `Money`: `import { Money, formatMoney } from "@/components/money";`. Add `currency` to the `columns` memo dependency array (`}, [isJoint, people, currency]);`).

- [ ] **Step 3b: The other five pages** — same two-line change each:

For `Overview.tsx`, `Budgets.tsx`, `NetWorth.tsx`, `Recurring.tsx`, `Goals.tsx`:
1. Add `import { useCurrency } from "@/lib/currency";` and `const { currency } = useCurrency();` in the component.
2. In the data-loading `useEffect`, pass `display: currency` to the getter (e.g. `getOverview({ personId, month, display: currency })`) and add `currency` to that effect's dependency array.

No `<Money>`/`formatMoney(n)` call site needs changing for value selection — values already arrive in display currency, and `Money` formats with the active symbol via context. (For NetWorth account rows, optionally pass `original={{ amount: a.original_balance!, currency: a.currency as Currency }}` to `<Money>` to surface foreign-held balances — only where `a.currency !== currency`.)

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm run test`
Expected: PASS (Transactions Original column present; other page tests still green — wrap any failing render in `<CurrencyProvider>`).

- [ ] **Step 5: Commit**

```bash
git add web/src/pages/Transactions.tsx web/src/pages/Overview.tsx web/src/pages/Budgets.tsx web/src/pages/NetWorth.tsx web/src/pages/Recurring.tsx web/src/pages/Goals.tsx web/src/pages/Transactions.test.tsx
git commit -m "feat(web): pages refetch on currency toggle + Transactions Original column"
```

---

### Task 12: Settings — default currency + read-only FX inspect

**Files:**
- Modify: `web/src/pages/Settings.tsx`
- Modify: `web/src/lib/api.ts` (add `getFxRates`)
- Test: `web/src/pages/Settings.test.tsx` (extend)

**Interfaces:**
- Consumes: `useCurrency`, a new `getFxRates()` API call.
- Produces: a **Money** `frosted-card` section with a `$ USD | ₪ ILS` default-currency control (writes `setCurrency`) and a read-only FX panel: source, last fetched, rate count + range.

- [ ] **Step 1: Add the API call** (`web/src/lib/api.ts`)

```ts
export type FxRatesInfo = {
  source: string | null; last_fetched: string | null; count: number;
  rates: { rate_date: string; base: string; quote: string; rate: number; source: string }[];
};
export const getFxRates = () => apiGet<FxRatesInfo>("/fx/rates");
```

- [ ] **Step 2: Write the failing test** (`web/src/pages/Settings.test.tsx`)

```tsx
// render Settings inside <CurrencyProvider>, mock getFxRates -> { count: 0, ... };
// assert the "Money" section heading and a "Display currency" control render.
test("renders a Money section with a currency control", async () => {
  // ...mock getPeople/getCategories/getVendors/getFxRates...
  expect(await screen.findByText(/Money/i)).toBeInTheDocument();
  expect(screen.getByRole("button", { name: /USD/ })).toBeInTheDocument();
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd web && npm run test -- Settings`
Expected: FAIL — no Money section.

- [ ] **Step 4: Add the section** (`web/src/pages/Settings.tsx`)

Add imports: `import { useCurrency, type Currency } from "@/lib/currency";` and `import { getFxRates, type FxRatesInfo } from "@/lib/api";`. In the component add:

```tsx
  const { currency, setCurrency } = useCurrency();
  const [fx, setFx] = useState<FxRatesInfo | null>(null);
  useEffect(() => { getFxRates().then(setFx).catch(() => setFx(null)); }, []);
  const CUR: { key: Currency; label: string }[] = [{ key: "USD", label: "$ USD" }, { key: "ILS", label: "₪ ILS" }];
```

Insert this `section` after the People section:

```tsx
      <section className="frosted-card" style={{ padding: 20, display: "grid", gap: 12 }}>
        <h2 style={h2}>Money</h2>
        <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
          <span style={{ fontSize: 13, color: "var(--fl-muted)" }}>Default display currency</span>
          {CUR.map((c) => (
            <button key={c.key} onClick={() => setCurrency(c.key)} aria-pressed={currency === c.key}
              style={{ ...pill, fontWeight: currency === c.key ? 700 : 500,
                       background: currency === c.key ? "var(--persona)" : "transparent",
                       color: currency === c.key ? "#fff" : "var(--fl-ink)" }}>
              {c.label}
            </button>
          ))}
        </div>
        <div style={{ fontSize: 12, color: "var(--fl-muted)" }}>
          {fx && fx.count > 0
            ? `Rates: ${fx.source ?? "—"}, last fetched ${fx.last_fetched ?? "never"} · ${fx.count} cached`
            : "No exchange rates cached yet. Importing a non-USD statement fetches the rate it needs."}
        </div>
      </section>
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd web && npm run test -- Settings`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/Settings.tsx web/src/lib/api.ts web/src/pages/Settings.test.tsx
git commit -m "feat(web): Settings Money section — default currency + FX inspect"
```

---

## Self-Review

**Spec coverage (design §8, §3.7; master P1 list):**
- `CurrencyProvider` default USD + localStorage → Task 7. ✔
- Currency-aware `Money`/`formatMoney` + original marker → Task 8. ✔
- Top-bar pill (USD first) + provider wrap → Task 9. ✔
- `display` param on overview/budgets/networth/transactions/recurring/goals → Tasks 2–5. ✔
- `/fx` router (inspect, manual, opt-in refresh) → Task 6. ✔
- Per-surface re-express + Transactions Original column → Task 11. ✔
- Settings default-currency + read-only FX inspect → Task 12. ✔
- Net-worth native reconciliation (unchanged) → Task 4 (reconcile left untouched). ✔

**Shape decision (recorded):** P1 implements design §8's literal mechanism — endpoints return values *already converted for the active display* (a `display` query param), with originals preserved, and pages refetch on toggle (matching the app's existing persona/month refetch pattern). This is faithful to the spec ("the UI works under either shape"); it favors the codebase's thin-router pattern and keeps the USD default a true no-op (factor 1.0, zero network).

**Placeholder scan:** the only prose-only steps are the repetitive page edits in Task 11 Step 3b and the test scaffolds in Tasks 11–12, which name the exact getter, prop, and dependency-array change per file; the mechanism (Money/context) is fully coded in Tasks 7–8. No `TODO`/`TBD`.

**Type consistency:** `Currency` = `"USD"|"ILS"` is defined once in `currency.tsx` and imported by `money.tsx` and `api.ts`. `display_factor`/`base_txns`/`convert` signatures match P0 + Task 1. `original_amount`/`original_currency`/`amount_base`/`rate_stale` are produced by Task 2 and consumed by the `Transaction` type (Task 10) and the Original column (Task 11). `display` defaults to `"USD"` in every endpoint and is dropped from the query string when omitted.
