# Plan 9 — Settings Page Design

> Page-level addendum to `2026-06-18-finance-ui-rewrite-design.md` (§4 IA, §7 API).
> Covers the **Settings** page + its backend routers. Locked decisions below.

## Goal
A single place to manage the per-person rule data that drives categorization and drill-down:
**category keyword rules**, **vendor groups**, and **renaming people**. Reuses the engine's
category/vendor CRUD and the existing people rename endpoint. No engine changes.

## Key constraint — categories & vendors are per-person
Both tables have `person_id NOT NULL` (FK to people); there is **no shared/Joint scope** for
them. So the Settings page manages them for **one selected person at a time** via a person
selector (defaulting to the active persona, or the first person when the persona is Joint).
People rename is global (not persona-scoped).

## Backend contract
Two new thin routers; people rename already exists (`PATCH /api/people/{id}`).

`backend/api/categories.py` (prefix `/categories`):
- `GET /api/categories?person_id=<int>` (required) → `db.get_categories(person_id)`; rows
  `{ id, person_id, name, keywords, parent }`.
- `PUT /api/categories` body `{ person_id: int, name: str, keywords?: str="", parent?: str|null }`
  → `db.upsert_category` (upsert on `(person_id, name)`); `{ ok: true }`.
- `DELETE /api/categories/{id}` → `db.delete_category`; `{ ok: true }`.

`backend/api/vendors.py` (prefix `/vendors`): same shape, no `parent`:
- `GET /api/vendors?person_id=<int>` → `db.get_vendors`.
- `PUT /api/vendors` body `{ person_id, name, keywords? }` → `db.upsert_vendor`.
- `DELETE /api/vendors/{id}` → `db.delete_vendor`.

## Frontend (`web/src/pages/Settings.tsx`)
- **People** section: each person as an inline editable name (commit on blur → `renamePerson`,
  reusing `PATCH /people/{id}`); refetch after.
- **Person selector**: pill buttons (from `getPeople`) choosing whose categories/vendors to edit;
  defaults to the active persona's person (or first person for Joint).
- **Categories** + **Vendors** sections (identical UI, a shared `RuleSection`): list each rule's
  name + an inline editable **keywords** field (comma-separated; commit on blur → upsert), a ✕
  delete, and an always-visible add row (name + keywords + add button). `parent` is not edited
  here (drill-down rollups are out of scope).
- Refetch the relevant list after each mutation. Frosted Ledger styling; tabular numerals N/A.

## Out of scope
Category `parent`/rollup editing, deleting/adding people (seeded pair stays), bulk
recategorization, the privacy-info blurb (can be a later static addition). (Future.)
