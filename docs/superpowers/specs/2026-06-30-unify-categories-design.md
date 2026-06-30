# Unify Categories & Vendors Across Users — Design

**Date:** 2026-06-30
**Status:** Approved (design)

## Problem

Spending **categories** and **vendor groups** are stored per-person:

```
categories(id, person_id NOT NULL, name, keywords, parent)   UNIQUE(person_id, name)
vendors   (id, person_id NOT NULL, name, keywords)            UNIQUE(person_id, name)
```

Each person owns a private copy, seeded identically from `_STARTER_CATEGORIES` /
`_STARTER_VENDORS` at `init_db`. Transactions reference a category by **name**
(`transactions.category TEXT`), and budgets/rollups key off the name too.

Because the starter sets are seeded identically, cross-person sums and
comparisons *appear* to work today — but only coincidentally. As soon as either
person renames, adds, deletes, or re-keywords a category (or vendor), the
taxonomies diverge:

- the same merchant categorizes differently per person (keyword rules are per-person);
- rollups differ (parents are per-person);
- a category one person creates doesn't exist for the other → comparison gaps.

This defeats the goal: a **shared taxonomy** is what lets the app compare, sum,
and roll up spending consistently across everyone (e.g. the side-by-side
per-category comparison in `analysis.py`).

## Goal

Make categories and vendor groups **global / household-wide** — one shared set
used by all people — so cross-user comparison and aggregation are reliable.

Out of scope:
- The deprecated Streamlit `app.py` (README: deprecated). It will not be updated and may break; the live stack is `modules/` + `backend/` (FastAPI) + `web/` (React).
- Normalizing `transactions.category` to a foreign-key id. The whole app is name-keyed; names are preserved by the migration, so no transaction changes are needed.
- `budgets`/`goals`/`accounts` person scoping (who is budgeting/saving) — a separate axis from the taxonomy, unchanged.

## Approach

Convert `categories` and `vendors` to **global tables keyed by name**, preserving
the existing name-as-key design. Decisions taken during design:

- **Unify both** categories *and* vendors (identical structure, both power cross-person comparison).
- **Keep `person_id` in the HTTP API and React calls but ignore it** — minimise frontend churn. The database layer drops person scoping; the API/React keep passing a now-ignored `person_id`.

### Schema

Rebuild both tables (SQLite: create-new → copy-merged → drop-old → rename):

```
categories(id INTEGER PK, name TEXT UNIQUE NOT NULL, keywords TEXT DEFAULT '', parent TEXT DEFAULT '')
vendors   (id INTEGER PK, name TEXT UNIQUE NOT NULL, keywords TEXT DEFAULT '')
```

### Migration (one-time, in `init_db`, idempotent)

Guarded by detecting the **old** schema (a `person_id` column present on
`categories`/`vendors`). When detected:

1. Read all rows across all people.
2. **Merge by name** (exact name match):
   - **keywords**: union the comma-separated rules across people; trim, dedupe case-insensitively, re-join.
   - **parent** (categories only): take the non-empty parent; if people disagree with multiple distinct non-empty parents, pick deterministically (most frequent, ties broken alphabetically).
3. Write merged rows into the new global table; drop the old; rename.

Because every name from every person is unioned in, **no existing
transaction's category name is orphaned**.

Seeding changes from a per-person loop to a **seed-once-when-empty** global seed
of `_STARTER_CATEGORIES` / `_STARTER_VENDORS`.

### Database functions (`modules/database.py`)

Drop `person_id` from the taxonomy functions (global now):

- `get_categories()`, `category_parents()`, `upsert_category(name, keywords, parent=None)`, `delete_category(id)`
- `get_vendors()`, `upsert_vendor(name, keywords)`, `group_vendor(target, keyword)`, `ungroup_vendor(target, keyword)`, `delete_vendor(id)`

`get_categories` / `get_vendors` accept an optional ignored `person_id=None` so
existing call sites that still pass it keep working.

### Backend API (`backend/api/`)

Endpoints keep their `person_id` query/body param (ignored) so the React client
is untouched:

- `categories.py`: `list_categories(person_id)` → `db.get_categories()`; `upsert_category(body)` → `db.upsert_category(body.name, body.keywords, body.parent)`; delete unchanged. `CategoryUpsert.person_id` stays (ignored).
- `imports.py`: `_category_rules()` → `db.get_categories()` (auto-tagging now uses the shared rules — a side benefit: every import tags consistently regardless of person).
- `budgets.py`, `analysis.py`: `db.category_parents()` (global). Today these pass `{}` for the Joint view because there was no shared taxonomy; with global parents, **Joint rollups now work** — an improvement, verified against budget rollup tests.
- `vendors.py`: same treatment as categories.

### Frontend (`web/`)

- `lib/api.ts`: `getCategories(personId)` / `getVendors(personId)` keep passing the (ignored) `personId`. Relax `Category.person_id` / `Vendor.person_id` to optional (`person_id?: number | null`) since the global rows no longer carry it.
- `pages/Settings.tsx`: the categories & vendor-group editors now show/edit the single shared list regardless of the selected person. The mutation guards (`selected != null`) still hold (a person is always selected). The person picker no longer affects these two sections — hide it for the Categories/Vendor-groups panels (small UX cleanup) so it isn't misleading.

## Data flow (unchanged for the user)

Import → auto-categorize using the shared keyword rules → transactions store the
category name → analysis/budgets/overview aggregate by name across all people
against one taxonomy.

## Edge cases

- **Conflicting keyword rules** across people for the same category → unioned (the merged category matches any of the prior rules).
- **Conflicting parents** → deterministic pick (documented), surfaced in a migration log line.
- **A name only one person had** → preserved in the shared set; that person's transactions stay categorized; now available to everyone.
- **Re-run / already-migrated DB** → guard sees no `person_id` column → no-op.
- **Empty DB / fresh install** → global seed runs once.

## Testing

- **Migration test**: build a DB in the *old* per-person shape with divergent rows (same name different keywords; same name different parents; a name unique to one person), run `init_db`, assert: single global table, keyword union, deterministic parent, all names present, transactions still resolve.
- **Idempotency test**: run `init_db` twice → stable, no duplicate rows or data loss.
- **db unit tests**: `get_categories()/upsert_category()/category_parents()` and the vendor equivalents operate globally (no person scoping).
- **API tests**: `GET /categories?person_id=…` returns the same global list for any person_id; `PUT` upserts globally; vendors likewise.
- **Rollup tests**: `category_parents()` now applies to the Joint view (budgets/analysis) — extend existing budget rollup tests to assert Joint rollups.
- **Frontend tests**: `api.test.ts` still builds the category/vendor URLs; `Settings.test.tsx` renders the shared list and mutations call the upserts. Adjust any test asserting per-person isolation.
- Full `pytest` + `npm --prefix web test` green.
