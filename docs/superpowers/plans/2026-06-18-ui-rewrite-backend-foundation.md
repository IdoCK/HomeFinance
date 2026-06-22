# UI Rewrite — Plan 1: Backend Foundation (FastAPI) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up a thin FastAPI layer that exposes the existing Python engine (`modules/`) and SQLite database over JSON — people, transactions, and the Overview aggregate — fully tested, with the Streamlit app still running untouched.

**Architecture:** FastAPI app factory (`create_app()`) mounts JSON routers under `/api/*`, each delegating directly to existing `modules/database.py` and `modules/analytics.py` functions. No business logic in the API layer. Tests use FastAPI `TestClient` against a temp SQLite DB created by monkeypatching `modules.database.DB_PATH`.

**Tech Stack:** Python 3, FastAPI, Uvicorn, Pydantic v2, pandas (existing), pytest + httpx (TestClient).

## Global Constraints

- Local-only tool: no auth, no cloud, no network calls in this wave. (spec §1 non-goals)
- Reuse the engine unchanged: do NOT modify `modules/*.py` behavior; the API only calls into it. New logic, if ever needed, goes into `modules/`. (spec §2)
- Keep `data/finance.db` and its schema unchanged. (spec §1)
- Persona semantics: `person_id` omitted/None = Joint (all people merged), matching `database.get_transactions(person_id=None)`. (spec §4, §9)
- Money convention from the schema: `amount` negative = spend, positive = income. (database.py:87)
- Transaction dict keys returned by the engine: `id, person_id, date (ISO YYYY-MM-DD), description, amount, category, source, included (0/1), balance, person (name)`. (database.py:254-262)
- Single-port production later: the app must be able to serve a built SPA from `web/dist` if present, but must not fail when it is absent. (spec §2)

---

### Task 1: Backend package, app factory, health route, test harness

**Files:**
- Create: `app/__init__.py`
- Create: `app/main.py`
- Create: `app/api/__init__.py`
- Create: `tests/api/__init__.py`
- Create: `tests/api/conftest.py`
- Test: `tests/api/test_health.py`
- Modify: `requirements.txt`

**Interfaces:**
- Produces: `app.main.create_app() -> fastapi.FastAPI` (calls `database.init_db()` on build, mounts `/api` routers, serves `web/dist` if it exists). `app.main.app` module-level instance for `uvicorn app.main:app`.
- Produces (test): pytest fixture `client` (a `fastapi.testclient.TestClient` bound to a temp DB with the two seeded people) and `people` (list of seeded `{id, name}` dicts).

- [ ] **Step 1: Add backend dependencies**

Append to `requirements.txt`:

```
fastapi
uvicorn[standard]
python-multipart
httpx
```

Then install:

```bash
pip install -r requirements.txt
```

- [ ] **Step 2: Write the failing health test**

Create `tests/api/__init__.py` (empty), then `tests/api/conftest.py`:

```python
import importlib
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A TestClient bound to a fresh temp SQLite DB with the two seeded people."""
    from modules import database
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "test.db")
    database.init_db()  # creates schema + seeds "You" / "Spouse" into the temp db

    from app import main
    importlib.reload(main)  # rebuild app against the patched DB_PATH
    return TestClient(main.create_app())


@pytest.fixture()
def people(client):
    return client.get("/api/people").json()
```

Create `tests/api/test_health.py`:

```python
def test_health_ok(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/api/test_health.py -v`
Expected: FAIL (`ModuleNotFoundError: No module named 'app'` or 404).

- [ ] **Step 4: Create the package and app factory**

Create `app/__init__.py` (empty). Create `app/api/__init__.py` (empty). Create `app/main.py`:

```python
"""FastAPI layer over the existing finance engine. Thin: routers call modules/."""
from pathlib import Path

from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from modules import database as db

DIST_DIR = Path(__file__).resolve().parent.parent / "web" / "dist"

health = APIRouter()


@health.get("/health")
def health_check():
    return {"status": "ok"}


def create_app() -> FastAPI:
    db.init_db()
    app = FastAPI(title="HomeFinance API")

    # Dev only: the Vite dev server runs on :5173 and calls the API on :8000.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health, prefix="/api")

    # Production: serve the built SPA from web/dist when it exists. Absent in dev.
    if DIST_DIR.is_dir():
        app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="spa")

    return app


app = create_app()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/api/test_health.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add app tests/api requirements.txt
git commit -m "feat(api): FastAPI app factory, health route, test harness"
```

---

### Task 2: People endpoints

**Files:**
- Create: `app/api/people.py`
- Create: `app/schemas.py`
- Modify: `app/main.py` (register the people router)
- Test: `tests/api/test_people.py`

**Interfaces:**
- Consumes: `database.list_people()`, `database.rename_person(person_id, new_name)`.
- Produces: `GET /api/people -> [{"id": int, "name": str}]`; `PATCH /api/people/{id}` body `{"name": str}` -> the updated `{"id","name"}`.
- Produces: `app.schemas.PersonUpdate` (Pydantic) with field `name: str`.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_people.py`:

```python
def test_list_people_returns_two_seeded(client):
    r = client.get("/api/people")
    assert r.status_code == 200
    data = r.json()
    assert len(data) == 2
    assert {p["name"] for p in data} == {"You", "Spouse"}
    assert all(isinstance(p["id"], int) for p in data)


def test_rename_person(client, people):
    pid = people[0]["id"]
    r = client.patch(f"/api/people/{pid}", json={"name": "Avi"})
    assert r.status_code == 200
    assert r.json() == {"id": pid, "name": "Avi"}
    assert any(p["name"] == "Avi" for p in client.get("/api/people").json())
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_people.py -v`
Expected: FAIL (404 — router not registered).

- [ ] **Step 3: Create schema and router**

Create `app/schemas.py`:

```python
from pydantic import BaseModel


class PersonUpdate(BaseModel):
    name: str
```

Create `app/api/people.py`:

```python
from fastapi import APIRouter, HTTPException

from modules import database as db
from app.schemas import PersonUpdate

router = APIRouter(prefix="/people", tags=["people"])


@router.get("")
def list_people():
    return db.list_people()


@router.patch("/{person_id}")
def rename_person(person_id: int, body: PersonUpdate):
    if not any(p["id"] == person_id for p in db.list_people()):
        raise HTTPException(status_code=404, detail="person not found")
    db.rename_person(person_id, body.name)
    return {"id": person_id, "name": body.name}
```

- [ ] **Step 4: Register the router**

In `app/main.py`, add the import near the other imports:

```python
from app.api import people
```

And inside `create_app()`, immediately after `app.include_router(health, prefix="/api")`, add:

```python
    app.include_router(people.router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/api/test_people.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add app/api/people.py app/schemas.py app/main.py tests/api/test_people.py
git commit -m "feat(api): people list + rename endpoints"
```

---

### Task 3: Transactions list endpoint (persona-scoped)

**Files:**
- Create: `app/api/transactions.py`
- Modify: `app/main.py` (register the transactions router)
- Test: `tests/api/test_transactions.py`

**Interfaces:**
- Consumes: `database.get_transactions(person_id=None)`, `database.add_transactions(person_id, rows, file_hash=None)` (test setup only).
- Produces: `GET /api/transactions?person_id={int|omitted}` -> list of transaction dicts (keys per Global Constraints). Omitting `person_id` returns all people (Joint).

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_transactions.py`:

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def seeded(client, people):
    from modules import database as db
    you, spouse = people[0]["id"], people[1]["id"]
    db.add_transactions(you, [
        {"date": "2026-05-03", "description": "Whole Foods", "amount": -84.20,
         "category": "Groceries", "source": "card"},
        {"date": "2026-05-10", "description": "Paycheck", "amount": 4740.0,
         "category": "Income", "source": "bank"},
    ])
    db.add_transactions(spouse, [
        {"date": "2026-05-06", "description": "Chipotle", "amount": -31.55,
         "category": "Eating out", "source": "card"},
    ])
    return {"you": you, "spouse": spouse}


def test_all_transactions_when_no_person(client, seeded):
    r = client.get("/api/transactions")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_transactions_scoped_to_person(client, seeded):
    r = client.get("/api/transactions", params={"person_id": seeded["spouse"]})
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["description"] == "Chipotle"
    assert rows[0]["category"] == "Eating out"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_transactions.py -v`
Expected: FAIL (404 — router not registered).

- [ ] **Step 3: Create the router**

Create `app/api/transactions.py`:

```python
from typing import Optional

from fastapi import APIRouter

from modules import database as db

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("")
def list_transactions(person_id: Optional[int] = None):
    """person_id omitted -> all people (Joint)."""
    return db.get_transactions(person_id)
```

- [ ] **Step 4: Register the router**

In `app/main.py` add `from app.api import transactions` with the other imports, and inside `create_app()` after the people router add:

```python
    app.include_router(transactions.router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/api/test_transactions.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Commit**

```bash
git add app/api/transactions.py app/main.py tests/api/test_transactions.py
git commit -m "feat(api): persona-scoped transactions list"
```

---

### Task 4: Transaction update endpoint (category / included)

**Files:**
- Modify: `app/api/transactions.py` (add PATCH route)
- Modify: `app/schemas.py` (add `TransactionUpdate`)
- Test: `tests/api/test_transaction_update.py`

**Interfaces:**
- Consumes: `database.set_transaction_category(txn_id, category)`, `database.set_transaction_included(txn_id, included)`.
- Produces: `app.schemas.TransactionUpdate` with optional `category: str | None` and `included: bool | None`.
- Produces: `PATCH /api/transactions/{id}` body `{category?, included?}` -> the updated transaction dict. Applies whichever field(s) are present.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_transaction_update.py`:

```python
import pytest


@pytest.fixture()
def one_txn(client, people):
    from modules import database as db
    pid = people[0]["id"]
    db.add_transactions(pid, [
        {"date": "2026-05-03", "description": "Chewy", "amount": -52.0,
         "category": "Uncategorized", "source": "card"},
    ])
    return db.get_transactions(pid)[0]


def test_update_category(client, one_txn):
    r = client.patch(f"/api/transactions/{one_txn['id']}", json={"category": "Dog"})
    assert r.status_code == 200
    assert r.json()["category"] == "Dog"


def test_toggle_included(client, one_txn):
    r = client.patch(f"/api/transactions/{one_txn['id']}", json={"included": False})
    assert r.status_code == 200
    assert r.json()["included"] == 0


def test_update_missing_txn_404(client):
    r = client.patch("/api/transactions/999999", json={"category": "X"})
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_transaction_update.py -v`
Expected: FAIL (405/404 — PATCH route absent).

- [ ] **Step 3: Add the schema**

Append to `app/schemas.py`:

```python
from typing import Optional


class TransactionUpdate(BaseModel):
    category: Optional[str] = None
    included: Optional[bool] = None
```

- [ ] **Step 4: Add the PATCH route**

In `app/api/transactions.py`, add the import and route:

```python
from fastapi import HTTPException
from app.schemas import TransactionUpdate


@router.patch("/{txn_id}")
def update_transaction(txn_id: int, body: TransactionUpdate):
    rows = db.get_transactions()
    if not any(t["id"] == txn_id for t in rows):
        raise HTTPException(status_code=404, detail="transaction not found")
    if body.category is not None:
        db.set_transaction_category(txn_id, body.category)
    if body.included is not None:
        db.set_transaction_included(txn_id, body.included)
    return next(t for t in db.get_transactions() if t["id"] == txn_id)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/api/test_transaction_update.py -v`
Expected: PASS (3 passed).

- [ ] **Step 6: Commit**

```bash
git add app/api/transactions.py app/schemas.py tests/api/test_transaction_update.py
git commit -m "feat(api): update transaction category/included"
```

---

### Task 5: Overview aggregate endpoint

**Files:**
- Create: `app/api/overview.py`
- Modify: `app/main.py` (register the overview router)
- Test: `tests/api/test_overview.py`

**Interfaces:**
- Consumes: `database.get_transactions(person_id)`, `analytics.monthly_savings(txns) -> DataFrame[income, spend, savings, savings_rate, complete]` indexed by month label, `analytics.latest_complete_month(savings) -> label|None`, `analytics.category_totals(txns) -> {category: float}`.
- Produces: `GET /api/overview?person_id={int|omitted}&month={YYYY-MM|omitted}` -> 
  ```json
  {
    "month": "2026-05",
    "months": ["2026-04", "2026-05"],
    "income": 4740.0, "spend": 115.75, "net": 4624.25,
    "savings_rate": 0.976, "complete": false,
    "by_category": {"Groceries": 84.2, "Eating out": 31.55}
  }
  ```
  `month` defaults to the latest complete month, else the last month present. Empty data -> all numbers 0/None and empty lists/objects. NaN savings_rate is serialized as `null`.

- [ ] **Step 1: Write the failing tests**

Create `tests/api/test_overview.py`:

```python
import pytest


@pytest.fixture()
def seeded(client, people):
    from modules import database as db
    you = people[0]["id"]
    # A fully-covered May (1st..31st present) so it counts as a complete month.
    db.add_transactions(you, [
        {"date": "2026-05-01", "description": "Rent", "amount": -2000.0,
         "category": "Housing", "source": "bank"},
        {"date": "2026-05-10", "description": "Paycheck", "amount": 5000.0,
         "category": "Income", "source": "bank"},
        {"date": "2026-05-15", "description": "Whole Foods", "amount": -300.0,
         "category": "Groceries", "source": "card"},
        {"date": "2026-05-31", "description": "Chipotle", "amount": -100.0,
         "category": "Eating out", "source": "card"},
    ])
    return you


def test_overview_headline_numbers(client, seeded):
    r = client.get("/api/overview", params={"person_id": seeded, "month": "2026-05"})
    assert r.status_code == 200
    d = r.json()
    assert d["month"] == "2026-05"
    assert d["income"] == 5000.0
    assert d["spend"] == 2400.0
    assert d["net"] == 2600.0
    assert d["by_category"]["Housing"] == 2000.0
    assert "2026-05" in d["months"]


def test_overview_empty_data(client, people):
    r = client.get("/api/overview", params={"person_id": people[0]["id"]})
    assert r.status_code == 200
    d = r.json()
    assert d["income"] == 0 and d["spend"] == 0 and d["net"] == 0
    assert d["months"] == [] and d["by_category"] == {}
    assert d["savings_rate"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/api/test_overview.py -v`
Expected: FAIL (404 — router not registered).

- [ ] **Step 3: Create the overview router**

Create `app/api/overview.py`:

```python
from typing import Optional

import pandas as pd
from fastapi import APIRouter

from modules import database as db
from modules import analytics

router = APIRouter(prefix="/overview", tags=["overview"])


def _empty():
    return {"month": None, "months": [], "income": 0, "spend": 0, "net": 0,
            "savings_rate": None, "complete": False, "by_category": {}}


@router.get("")
def overview(person_id: Optional[int] = None, month: Optional[str] = None):
    txns = db.get_transactions(person_id)
    sav = analytics.monthly_savings(txns)
    if sav.empty:
        return _empty()

    recs = {}
    for idx, row in sav.iterrows():
        rate = row["savings_rate"]
        recs[str(idx)] = {
            "income": float(row["income"]),
            "spend": float(row["spend"]),
            "net": float(row["savings"]),
            "savings_rate": None if pd.isna(rate) else float(rate),
            "complete": bool(row["complete"]),
        }

    months = list(recs.keys())
    if month is None or month not in recs:
        latest = analytics.latest_complete_month(sav)
        month = str(latest) if latest is not None else months[-1]

    month_txns = [t for t in txns if (t.get("date") or "")[:7] == month]
    sel = recs[month]
    return {
        "month": month,
        "months": months,
        "income": sel["income"],
        "spend": sel["spend"],
        "net": sel["net"],
        "savings_rate": sel["savings_rate"],
        "complete": sel["complete"],
        "by_category": analytics.category_totals(month_txns),
    }
```

- [ ] **Step 4: Register the router**

In `app/main.py` add `from app.api import overview` with the other imports, and inside `create_app()` after the transactions router add:

```python
    app.include_router(overview.router, prefix="/api")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/api/test_overview.py -v`
Expected: PASS (2 passed).

- [ ] **Step 6: Run the full API suite**

Run: `pytest tests/api -v`
Expected: PASS (all tasks green).

- [ ] **Step 7: Commit**

```bash
git add app/api/overview.py app/main.py tests/api/test_overview.py
git commit -m "feat(api): overview aggregate endpoint"
```

---

### Task 6: Dev/prod run wiring + smoke check

**Files:**
- Create: `run_api.py`
- Modify: `README.md` (add a "Running the new API" section)
- Test: `tests/api/test_spa_serving.py`

**Interfaces:**
- Consumes: `app.main.create_app`.
- Produces: `python run_api.py` -> serves `app.main:app` on `:8000`. Behavior verified: with no `web/dist`, unknown non-API paths return 404 (not a crash); `/api/health` works.

- [ ] **Step 1: Write the failing test**

Create `tests/api/test_spa_serving.py`:

```python
def test_api_available_without_dist(client):
    # web/dist does not exist in dev/test; the app must still serve the API
    # and simply 404 unknown paths rather than crashing at startup.
    assert client.get("/api/health").status_code == 200
    assert client.get("/definitely-not-a-route").status_code == 404
```

- [ ] **Step 2: Run test to verify it passes (guards existing behavior)**

Run: `pytest tests/api/test_spa_serving.py -v`
Expected: PASS (the Task 1 factory already guards `DIST_DIR.is_dir()`). If it fails, fix `create_app()` so the static mount is conditional.

- [ ] **Step 3: Add the run entrypoint**

Create `run_api.py`:

```python
"""Run the new API (and, once built, the SPA) on http://localhost:8000."""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)
```

- [ ] **Step 4: Document it**

In `README.md`, add this section after the existing "## Run" section:

```markdown
## Run the new API (in development)
The React UI is served by a FastAPI layer that reuses the same engine and database.

```bash
pip install -r requirements.txt
python run_api.py        # http://localhost:8000 — /api/* JSON
```

The web frontend (added in a later wave) runs separately with `npm run dev` and
proxies to this API. In production the built frontend is served by this same
process, so only `python run_api.py` is needed.
```

- [ ] **Step 5: Smoke-test manually**

Run: `python run_api.py` then in another shell `curl -s http://localhost:8000/api/health`
Expected: `{"status":"ok"}`. Stop the server (Ctrl-C).

- [ ] **Step 6: Commit**

```bash
git add run_api.py README.md tests/api/test_spa_serving.py
git commit -m "chore(api): dev run entrypoint + README + SPA-serving guard test"
```

---

## Self-Review

**1. Spec coverage (this wave = spec §11 wave 1 + foundations of §2, §7):**
- §2 thin FastAPI over `modules/` + SQLite → Task 1 (factory), all routers delegate directly. ✓
- §2 serve `web/dist` if present, no Node in prod → Task 1 conditional mount + Task 6 test. ✓
- §7 endpoints: people (Task 2), transactions list (Task 3), transaction update (Task 4), overview (Task 5). ✓ Remaining §7 endpoints (budgets, goals, networth, recurring, analytics, import, insights, agent) are explicitly deferred to later-wave plans.
- §4/§9 persona = `person_id` omitted → all → Tasks 3 & 5. ✓
- §10 API tested with TestClient + temp SQLite fixture → conftest + every task. ✓
- Streamlit untouched / engine unchanged → no `modules/*` or `app.py` edits in any task. ✓

**2. Placeholder scan:** No TBD/TODO; every code step shows complete code; every run step shows the exact command and expected result. ✓

**3. Type consistency:** `create_app()` defined in Task 1, imported by tests and `run_api.py` (Task 6). `PersonUpdate` (Task 2) and `TransactionUpdate` (Task 4) both live in `app/schemas.py`. Transaction dict keys used in tests (`id, category, included, description`) match the Global Constraints list. `monthly_savings` columns used in Task 5 (`income, spend, savings, savings_rate, complete`) match analytics.py:62-90. ✓

**Out of scope (next plans):** frontend scaffold (Vite + shadcn init, tokens, app shell, persona context), the per-page UIs, the import wizard + agent endpoints, AI Insights. Each gets its own plan written against the shapes established here.
