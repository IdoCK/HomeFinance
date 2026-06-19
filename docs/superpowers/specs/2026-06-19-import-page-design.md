# Plan 11 — Import Wizard Design

> Page-level addendum to `2026-06-18-finance-ui-rewrite-design.md` (§6 import flow, §7 API).
> Covers the **Import** page + its backend router. Locked decisions below.

## Goal
Replace the dense single-tab import with a guided **wizard** that preserves the local-agent
magic: drop a bank/card/Amazon export, the on-machine LLM (Ollama) figures out its layout,
you review + fix the parsed rows, then commit. Reuses `modules/agent_parser.py`,
`modules/parsing.py`, and `modules/database.py` unchanged. Nothing leaves the machine.

## Signature
The **local-agent indicator** + a quiet 3-step stepper. The "magic" is that a local model
parses arbitrary formats with no cloud call — so the page foregrounds an Ollama-ready chip
(🟢 ready / 🔴 offline with the fix) and a calm step progression. No showpiece gradient here
(that is reserved for AI Insights); this page is disciplined and utilitarian.

## Per-person import (persona gate)
Transactions belong to one person. **Joint** has no single owner, so importing requires a
concrete person — in Joint view the wizard shows a gentle gate ("Switch to You or Spouse to
import"). You / Spouse import straight away with that `person_id`.

## Steps
1. **Drop file** — file picker + a source select (auto · amazon · card · bank) + the Ollama
   chip. "Parse file" runs the agent (await + spinner; see deferrals re: streaming).
2. **Review** — a preview table: date · description · amount · editable category · include
   toggle. Any parser warnings show in a banner. "Import N transactions" commits.
3. **Done** — imported count + "Import another file" reset.

A file already imported for this person (matched by content hash) is caught at parse and shown
as an "already imported" notice instead of a duplicate review.

## Backend contract — `backend/api/imports.py` (prefix `/import`)
- `GET /api/import/status` → `agent_parser.check_ollama()` → `{ ok: bool, message: str }`
  (always 200 — offline is a normal state the UI renders, not an error).
- `POST /api/import/parse` (multipart: `file`, `source` form, `person_id` form) → reads bytes,
  `file_hash = sha256`. If already imported → `{ already_imported: true, file_hash, filename }`.
  Else `agent_parser.parse_file_with_agent(bytes, filename, source, parsing.categorize,
  category_rules)` → `{ already_imported: false, file_hash, filename, source, rows, warnings }`.
  `rows` = `[{date, description, amount, category, source, included, balance}]`.
- `POST /api/import/commit` body `{ person_id, filename, file_hash, source, rows[] }` →
  `db.add_transactions(person_id, rows, file_hash)` + `db.record_import(...)` → `{ imported: n }`.

## Frontend (`web/src/pages/Import.tsx`)
A small state machine (`step: "upload" | "review" | "done"`). Reuses the Frosted Ledger card +
pill styling and `--persona` accent. The review table reuses the same inline-edit feel as the
Transactions page (category text input, include checkbox) — kept simple, no TanStack here.

## Out of scope / deferred (ponytail — documented for the debt ledger)
- **Progress streaming (SSE/polling)** — v1 awaits the parse with a spinner. (Spec §13 lists
  this as optional; revisit if large files feel unresponsive.)
- **"Learn a new format"** UI (`agent_parser.propose_format`) — unknown files still parse via
  the agent; saving a reusable registry format is a later enhancement.
- **Keyword-rule learning on commit** (app.py `_learn_keyword`) — deferred; categorize still
  works, it just won't auto-teach merchants yet.
- **Statement-balance → Net Worth account refresh** (spec §6 step 3, marked optional) —
  `parse_file_with_agent` already discards the running balance; wire later via a dedicated path.
- **Drag-and-drop** polish — a plain file picker is enough for v1.
