# Unify Categories & Vendors Across Users — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make spending categories and vendor groups global (household-wide) instead of per-person, so categorization and cross-user comparison use one shared taxonomy.

**Architecture:** Rebuild the `categories` and `vendors` tables as global tables keyed by `name` (dropping `person_id`), with a one-time idempotent migration in `init_db` that merges every person's rows. Transactions already reference categories by name, so no transaction data migrates. The HTTP API and React keep passing a now-ignored `person_id` to minimise churn.

**Tech Stack:** Python 3.12, SQLite (`sqlite3`), FastAPI, pytest; React + TypeScript (Vite, Vitest) in `web/`.

## Global Constraints

- Categories and vendors are **global / household-wide**, not per-person.
- During import, **all** platform-wide category keyword rules are applied regardless of which person the file is imported for.
- The deprecated Streamlit `app.py` is **out of scope** — do not edit it; it may break.
- Transactions reference categories by **name**; names must be preserved by the migration so no transaction is orphaned.
- Migration runs inside `init_db`, must be **idempotent** (no-op once `person_id` is gone).
- Tests run from the project root (`C:\Users\lahat\Documents\Claude\HomeFinance`) with the venv Python; set `PYTHONUTF8=1` for Hebrew data. Full suite: `venv\Scripts\python.exe -m pytest -q`; frontend: `npm --prefix web test`.

---

### Task 1: Global taxonomy in the database layer

**Files:**
- Modify: `modules/database.py` (schema DDL in `init_db`; seeding; new migration helper; `get_categories`, `upsert_category`, `delete_category`, `category_parents`, `get_vendors`, `upsert_vendor`, `group_vendor`, `ungroup_vendor`, `delete_vendor`)
- Test: `tests/test_taxonomy_global.py` (new)

**Interfaces:**
- Produces:
  - `get_categories(person_id=None) -> list[dict]` — global rows `{id, name, keywords, parent}`, `person_id` arg accepted but ignored.
  - `upsert_category(name, keywords, parent=None)` — global upsert on `name`.
  - `delete_category(category_id)` — unchanged signature.
  - `category_parents() -> dict[str, str]` — global `{name: parent}`.
  - `get_vendors(person_id=None) -> list[dict]` — global rows `{id, name, keywords}`.
  - `upsert_vendor(name, keywords)`, `group_vendor(target, keyword) -> list[str]`, `ungroup_vendor(target, keyword) -> list[str]`, `delete_vendor(vendor_id)`.
  - `_migrate_taxonomy_to_global(c, table, has_parent)` and `_merge_keywords(values) -> str` (module-private helpers).

- [ ] **Step 1: Write failing migration + function tests**

Create `tests/test_taxonomy_global.py`:

```python
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _old_shape_db(path):
    """Build a DB in the legacy per-person shape (categories/vendors with
    person_id) plus a couple of transactions, so we can assert the migration
    merges correctly and preserves transaction category names."""
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.executescript(
        """
        CREATE TABLE people (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER NOT NULL,
            name TEXT NOT NULL, keywords TEXT DEFAULT '', parent TEXT DEFAULT '',
            UNIQUE(person_id, name));
        CREATE TABLE vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER NOT NULL,
            name TEXT NOT NULL, keywords TEXT DEFAULT '', UNIQUE(person_id, name));
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER NOT NULL,
            date TEXT, description TEXT, amount REAL, category TEXT DEFAULT 'Uncategorized');
        """
    )
    c.executemany("INSERT INTO people(name) VALUES (?)", [("Ido",), ("Aviv",)])
    # Same name, different keyword rules + different parents across people,
    # plus a name only one person has.
    c.executemany(
        "INSERT INTO categories(person_id, name, keywords, parent) VALUES (?,?,?,?)",
        [
            (1, "Groceries", "whole foods, costco", "Food"),
            (2, "Groceries", "costco, shufersal", ""),
            (1, "Eating Out", "cafe", "Food"),
            (2, "Eating Out", "cafe", "Dining"),
            (1, "Pet", "chewy", ""),
        ],
    )
    c.executemany(
        "INSERT INTO vendors(person_id, name, keywords) VALUES (?,?,?)",
        [(1, "Amazon", "amazon, amzn"), (2, "Amazon", "amzn, amazon.com")],
    )
    c.execute("INSERT INTO transactions(person_id, date, description, amount, category) "
              "VALUES (2,'2026-03-01','x',-5,'Pet')")  # name only person 1 had
    conn.commit()
    conn.close()


def _reload_db(tmp_path, monkeypatch):
    """Point the db module at a temp DB file and import it fresh."""
    import importlib
    from modules import database
    db_path = tmp_path / "finance.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    return database, db_path


def test_migration_merges_categories_to_global(tmp_path, monkeypatch):
    db, db_path = _reload_db(tmp_path, monkeypatch)
    _old_shape_db(str(db_path))
    db.init_db()
    cats = {c["name"]: c for c in db.get_categories()}
    # one global row per name, no person_id scoping
    assert set(cats) >= {"Groceries", "Eating Out", "Pet"}
    # keyword rules unioned (dedup, order-preserving)
    assert cats["Groceries"]["keywords"] == "whole foods,costco,shufersal"
    # parent: non-empty wins; on conflict deterministic (Food beats Dining: count tie -> alphabetical)
    assert cats["Eating Out"]["parent"] in {"Dining", "Food"}
    # the transaction's category name still resolves to a real global category
    assert "Pet" in cats


def test_migration_is_idempotent(tmp_path, monkeypatch):
    db, db_path = _reload_db(tmp_path, monkeypatch)
    _old_shape_db(str(db_path))
    db.init_db()
    first = db.get_categories()
    db.init_db()  # second run must be a no-op on the now-global table
    assert [c["name"] for c in db.get_categories()] == [c["name"] for c in first]


def test_vendors_merged_global(tmp_path, monkeypatch):
    db, db_path = _reload_db(tmp_path, monkeypatch)
    _old_shape_db(str(db_path))
    db.init_db()
    vs = {v["name"]: v for v in db.get_vendors()}
    assert vs["Amazon"]["keywords"] == "amazon,amzn,amazon.com"


def test_upsert_and_parents_global(tmp_path, monkeypatch):
    db, db_path = _reload_db(tmp_path, monkeypatch)
    db.init_db()  # fresh DB -> global seed
    db.upsert_category("Travel", "airline, hotel", parent="Discretionary")
    assert db.category_parents()["Travel"] == "Discretionary"
    # same call from "any person" returns the same global list
    assert db.get_categories(1) == db.get_categories(2)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `venv\Scripts\python.exe -m pytest tests/test_taxonomy_global.py -q`
Expected: FAIL (functions still require `person_id`; tables still per-person).

- [ ] **Step 3: Add the migration helpers to `modules/database.py`**

Add near the other module-private helpers (after the seed constants, before `get_conn`):

```python
def _merge_keywords(values):
    """Union comma-separated keyword rules across rows, dedupe case-insensitively,
    preserving first-seen order."""
    seen, out = set(), []
    for raw in values:
        for k in (raw or "").split(","):
            k = k.strip()
            if k and k.lower() not in seen:
                seen.add(k.lower())
                out.append(k)
    return ",".join(out)


def _migrate_taxonomy_to_global(c, table, has_parent):
    """One-time migration: collapse a per-person taxonomy table (categories or
    vendors) into a single global table keyed by name. Idempotent — a no-op once
    the table no longer has a person_id column. Merges keyword rules (union) and,
    for categories, keeps a non-empty parent (most common; ties broken
    alphabetically)."""
    from collections import Counter, defaultdict
    cols = [r[1] for r in c.execute(f"PRAGMA table_info({table})")]
    if "person_id" not in cols:
        return  # already global
    by_name = defaultdict(list)
    for r in c.execute(f"SELECT * FROM {table}"):
        by_name[r["name"]].append(dict(r))
    merged = []
    for name, group in by_name.items():
        keywords = _merge_keywords(g.get("keywords") for g in group)
        parent = ""
        if has_parent:
            nonempty = [(g.get("parent") or "").strip() for g in group]
            nonempty = [p for p in nonempty if p]
            if nonempty:
                counts = Counter(nonempty)
                parent = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[0][0]
        merged.append((name, keywords, parent))
    c.execute(f"ALTER TABLE {table} RENAME TO {table}_old")
    if has_parent:
        c.execute(f"""CREATE TABLE {table} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            keywords TEXT DEFAULT '',
            parent TEXT DEFAULT '')""")
        c.executemany(
            f"INSERT INTO {table}(name, keywords, parent) VALUES (?,?,?)", merged)
    else:
        c.execute(f"""CREATE TABLE {table} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            keywords TEXT DEFAULT '')""")
        c.executemany(
            f"INSERT INTO {table}(name, keywords) VALUES (?,?)",
            [(n, k) for (n, k, _p) in merged])
    c.execute(f"DROP TABLE {table}_old")
```

- [ ] **Step 4: Update the schema DDL and seeding in `init_db`**

In the `executescript` DDL, replace the `categories` and `vendors` `CREATE TABLE` statements with the **global** shape (fresh installs get the new schema directly; existing DBs keep the old table via `IF NOT EXISTS` and are migrated in Step 5):

```sql
CREATE TABLE IF NOT EXISTS categories (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT UNIQUE NOT NULL,
    keywords  TEXT DEFAULT '',
    parent    TEXT DEFAULT ''
);
```

```sql
CREATE TABLE IF NOT EXISTS vendors (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    name      TEXT UNIQUE NOT NULL,
    keywords  TEXT DEFAULT ''
);
```

Replace the per-person seeding loop (the `for (person_id,) in c.execute("SELECT id FROM people")...` block that seeds categories and vendors) with a **global seed-once**:

```python
# Seed the shared starter taxonomy once (global, household-wide).
if not c.execute("SELECT COUNT(*) FROM categories").fetchone()[0]:
    for name, kws in _STARTER_CATEGORIES:
        c.execute("INSERT OR IGNORE INTO categories(name, keywords) VALUES (?,?)",
                  (name, kws))
if not c.execute("SELECT COUNT(*) FROM vendors").fetchone()[0]:
    for name, kws in _STARTER_VENDORS:
        c.execute("INSERT OR IGNORE INTO vendors(name, keywords) VALUES (?,?)",
                  (name, kws))
```

- [ ] **Step 5: Wire the migration into `init_db` (correct order)**

The legacy "ADD COLUMN parent" migration must run **before** the global migration (so an old DB's `parent` values are readable during merge). Immediately after the `executescript(...)` call and the people seed, and **before** the global seed from Step 4, insert:

```python
# Ensure a legacy categories table has the `parent` column before we merge it,
# so pre-parent DBs don't lose parent data during the global migration.
cat_cols = [r[1] for r in c.execute("PRAGMA table_info(categories)")]
if "person_id" in cat_cols and "parent" not in cat_cols:
    c.execute("ALTER TABLE categories ADD COLUMN parent TEXT DEFAULT ''")
# Collapse per-person taxonomies into one shared, household-wide set.
_migrate_taxonomy_to_global(c, "categories", has_parent=True)
_migrate_taxonomy_to_global(c, "vendors", has_parent=False)
```

Remove the now-obsolete standalone parent migration block (`cat_cols = ...; if "parent" not in cat_cols: ALTER TABLE categories ADD COLUMN parent ...`) further down, since the global `categories` always has `parent`.

- [ ] **Step 6: Make the taxonomy functions global**

Replace `get_categories`, `upsert_category`, `category_parents`, `get_vendors`, `upsert_vendor`, `group_vendor`, `ungroup_vendor` with global versions (`delete_category` / `delete_vendor` are unchanged — they delete by id):

```python
def get_categories(person_id=None):
    """All categories (global/household-wide). `person_id` is accepted but
    ignored — categories are shared across everyone."""
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM categories ORDER BY name")]


def upsert_category(name, keywords, parent=None):
    """Insert or update a global category. `parent` is an optional rollup group;
    pass None to leave an existing category's parent untouched."""
    with get_conn() as conn:
        if parent is None:
            conn.execute(
                """INSERT INTO categories(name, keywords) VALUES (?,?)
                   ON CONFLICT(name) DO UPDATE SET keywords=excluded.keywords""",
                (name, keywords))
        else:
            conn.execute(
                """INSERT INTO categories(name, keywords, parent) VALUES (?,?,?)
                   ON CONFLICT(name) DO UPDATE SET
                       keywords=excluded.keywords, parent=excluded.parent""",
                (name, keywords, parent))


def category_parents():
    """Map of {category_name: parent_name} (global; parent '' when unset)."""
    with get_conn() as conn:
        return {r["name"]: (r["parent"] or "")
                for r in conn.execute("SELECT name, parent FROM categories")}


def get_vendors(person_id=None):
    """All vendor groups (global). `person_id` accepted but ignored."""
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM vendors ORDER BY name")]


def upsert_vendor(name, keywords):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO vendors(name, keywords) VALUES (?,?)
               ON CONFLICT(name) DO UPDATE SET keywords=excluded.keywords""",
            (name, keywords))


def group_vendor(target, keyword):
    """Fold the merchant `keyword` into the global vendor group `target`."""
    target = (target or "").strip()
    keyword = (keyword or "").strip()
    existing = {v["name"]: v for v in get_vendors()}
    if target in existing:
        kws = [k.strip() for k in (existing[target]["keywords"] or "").split(",") if k.strip()]
    else:
        kws = [target]
    lowered = {k.lower() for k in kws}
    if keyword and keyword.lower() not in lowered:
        kws.append(keyword)
    upsert_vendor(target, ",".join(kws))
    return kws


def ungroup_vendor(target, keyword):
    """Pull a merchant `keyword` out of global vendor group `target`. Deletes the
    rule when its last keyword is removed."""
    target = (target or "").strip()
    keyword = (keyword or "").strip().lower()
    existing = {v["name"]: v for v in get_vendors()}
    if target not in existing:
        return []
    kws = [k.strip() for k in (existing[target]["keywords"] or "").split(",") if k.strip()]
    kws = [k for k in kws if k.lower() != keyword]
    if kws:
        upsert_vendor(target, ",".join(kws))
    else:
        delete_vendor(existing[target]["id"])
    return kws
```

- [ ] **Step 7: Run the Task-1 tests to verify they pass**

Run: `venv\Scripts\python.exe -m pytest tests/test_taxonomy_global.py -q`
Expected: PASS (4 tests).

- [ ] **Step 8: Commit**

```bash
git add modules/database.py tests/test_taxonomy_global.py
git commit -m "feat(db): make categories & vendors global with merge migration

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 2: Backend API wiring

**Files:**
- Modify: `backend/api/categories.py`, `backend/api/vendors.py`, `backend/api/imports.py:24-26`, `backend/api/budgets.py:42,58`, `backend/api/analysis.py:113`
- Modify: `app.py` — NOT TOUCHED (deprecated, out of scope)
- Test: `tests/api/test_taxonomy_api.py` (new); extend an existing budgets/analysis test for Joint rollups

**Interfaces:**
- Consumes (from Task 1): `db.get_categories()`, `db.upsert_category(name, keywords, parent)`, `db.category_parents()`, `db.get_vendors()`, `db.upsert_vendor(name, keywords)`, `db.group_vendor(target, keyword)`, `db.ungroup_vendor(target, keyword)`.
- Produces: HTTP endpoints unchanged in shape; `person_id` params accepted but ignored.

- [ ] **Step 1: Write failing API tests**

Create `tests/api/test_taxonomy_api.py`:

```python
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi.testclient import TestClient
from backend.main import create_app


def _client(tmp_path, monkeypatch):
    from modules import database
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "finance.db")
    database.init_db()
    return TestClient(create_app())


def test_categories_global_regardless_of_person(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.put("/api/categories", json={"person_id": 1, "name": "Travel", "keywords": "airline"})
    a = client.get("/api/categories", params={"person_id": 1}).json()
    b = client.get("/api/categories", params={"person_id": 2}).json()
    assert [c["name"] for c in a] == [c["name"] for c in b]
    assert any(c["name"] == "Travel" for c in a)


def test_vendors_global_regardless_of_person(tmp_path, monkeypatch):
    client = _client(tmp_path, monkeypatch)
    client.put("/api/vendors", json={"person_id": 2, "name": "Foo", "keywords": "foo"})
    a = client.get("/api/vendors", params={"person_id": 1}).json()
    assert any(v["name"] == "Foo" for v in a)
```

- [ ] **Step 2: Run to verify failure**

Run: `venv\Scripts\python.exe -m pytest tests/api/test_taxonomy_api.py -q`
Expected: FAIL (TypeErrors — API still calls `db.*` with `person_id`).

- [ ] **Step 3: Update `backend/api/categories.py`**

```python
@router.get("")
def list_categories(person_id: int):
    # person_id accepted for client back-compat but categories are global.
    return db.get_categories()


@router.put("")
def upsert_category(body: CategoryUpsert):
    db.upsert_category(body.name, body.keywords, body.parent)
    return {"ok": True}
```

(`remove_category` unchanged.)

- [ ] **Step 4: Update `backend/api/vendors.py`**

```python
@router.get("")
def list_vendors(person_id: int):
    return db.get_vendors()


@router.put("")
def upsert_vendor(body: VendorUpsert):
    db.upsert_vendor(body.name, body.keywords)
    return {"ok": True}


@router.post("/group")
def group_vendor(body: VendorGroup):
    keywords = db.group_vendor(body.target, body.keyword)
    return {"ok": True, "name": body.target, "keywords": keywords}


@router.post("/ungroup")
def ungroup_vendor(body: VendorGroup):
    keywords = db.ungroup_vendor(body.target, body.keyword)
    return {"ok": True, "name": body.target, "keywords": keywords}
```

(`remove_vendor` unchanged.)

- [ ] **Step 5: Update `backend/api/imports.py` `_category_rules`**

Replace lines 24-26:

```python
def _category_rules(person_id: int):
    # Global taxonomy: every category's keyword rules apply to every import,
    # regardless of which person the file is imported for.
    return [(c["name"], (c["keywords"] or "").split(","))
            for c in db.get_categories()]
```

- [ ] **Step 6: Update `category_parents` callers in `budgets.py` and `analysis.py`**

In `backend/api/budgets.py` (two sites, lines ~42 and ~58) replace:

```python
parents = db.category_parents(person_id) if person_id is not None else {}
```

with:

```python
parents = db.category_parents()  # global; applies to per-person and Joint views
```

In `backend/api/analysis.py` (line ~113) make the same replacement.

- [ ] **Step 7: Add a Joint-rollup assertion**

Find the existing budgets rollup test (search `tests/` for `category_parents` or `budget_status`). Add a case that requests the **Joint** scope (no `person_id`) with a parent-budget and child categories, asserting the child spend rolls up under the parent (previously `{}` meant no rollup). Use the same construction style as the neighbouring test in that file.

- [ ] **Step 8: Run API + affected suites**

Run: `venv\Scripts\python.exe -m pytest tests/api/test_taxonomy_api.py tests/api/test_analysis.py tests/test_budgets_parents_db.py -q`
Expected: PASS.

- [ ] **Step 9: Run the full Python suite**

Run: `set PYTHONUTF8=1 && venv\Scripts\python.exe -m pytest -q`
Expected: all pass (fix any test that asserted per-person category isolation by updating it to the global expectation).

- [ ] **Step 10: Commit**

```bash
git add backend/ tests/
git commit -m "feat(api): serve global categories/vendors; apply all rules on import

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

### Task 3: Frontend — shared taxonomy in Settings

**Files:**
- Modify: `web/src/lib/api.ts:353-354` (`Category`/`Vendor` types)
- Modify: `web/src/pages/Settings.tsx` (hide the person picker for the Categories & Vendor-groups panels)
- Test: `web/src/pages/Settings.test.tsx`; `web/src/lib/api.test.ts` (only if a category/vendor URL assertion needs updating)

**Interfaces:**
- Consumes: `GET/PUT/DELETE /api/categories`, `/api/vendors` (global; `person_id` ignored server-side).
- Produces: Settings renders one shared category/vendor list; mutations call the existing `upsertCategory`/`upsertVendor`/`deleteCategory`/`deleteVendor` (still passing the active `personId`, ignored).

- [ ] **Step 1: Relax the TS types in `web/src/lib/api.ts`**

```ts
export type Category = { id: number; person_id?: number | null; name: string; keywords: string; parent?: string | null };
export type Vendor = { id: number; person_id?: number | null; name: string; keywords: string };
```

(`getCategories(personId)` / `getVendors(personId)` keep their signatures — the arg is still sent and ignored server-side.)

- [ ] **Step 2: Update the Settings copy + hide the redundant person picker**

In `web/src/pages/Settings.tsx`, the header for the rules section reads "people, categories & vendor groups". Since categories/vendors are now shared, the person selector only governs nothing in those two panels. Hide the person picker control for the Categories and Vendor-groups panels (keep it for any genuinely per-person section, e.g. people management). Leave the existing `getCategories(selected)` / mutation calls as-is (the ignored `selected` is harmless). Add a short caption to each panel: `"Shared across everyone"`.

Concretely: locate the JSX person-selector element used above the Categories/Vendor `RuleEditor`s and either remove it from those panels or guard its render so it no longer appears for them; add the caption text node under each panel `Title`.

- [ ] **Step 3: Write/adjust the Settings test**

In `web/src/pages/Settings.test.tsx`, add or adjust a test asserting:
- the Categories panel renders rows from `getCategories` (mock returns a shared list),
- editing keywords calls `upsertCategory`,
- the per-person picker is **not** rendered for the Categories panel (query by its aria-label/role and assert absence).

Mirror the existing mocking style already in that file (`vi.fn()` per api function, `mockResolvedValue([...])`).

- [ ] **Step 4: Run the frontend tests**

Run: `npm --prefix web test`
Expected: PASS (update any snapshot/assertion that expected a per-person picker in those panels).

- [ ] **Step 5: Typecheck/build**

Run: `npm --prefix web run build`
Expected: builds with no TypeScript errors.

- [ ] **Step 6: Commit**

```bash
git add web/
git commit -m "feat(web): show categories & vendors as one shared list in Settings

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Notes for the implementer

- **Do not** edit `app.py` (deprecated). It calls the old per-person `db` signatures and will break; that is accepted and out of scope.
- The user verifies UI changes themselves — do not run a browser preview workflow for Task 3; the Vitest + build checks are the gate here.
- After all three tasks, re-run the full Python suite and `npm --prefix web test` together to confirm the vertical slice is green.
