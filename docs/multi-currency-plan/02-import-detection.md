# 02 — Import-Side Currency Detection

Sibling doc: 01 (conversion engine) owns the `fx_rates` table and amount
conversion. **This doc owns only detection + tagging at import time.** Contract
fields in §4 are the seam between the two; keep them stable.

---

## 1. Current import flow (as-built)

**Files**

- `backend/api/imports.py` — router. `POST /import/parse` (multipart: `file`,
  `source`, `person_id`) → returns candidate `rows` + `warnings` (no DB write).
  `POST /import/commit` (`ImportCommit`) → `db.add_transactions` + `record_import`.
  Dedup: sha256 of file bytes per person via `imported_files`.
- `modules/formats.py` — deterministic registry. `load_formats()` reads
  `csv_formats.md`; `match_format()` scores layouts by header signature +
  `file_contains`; `parse_with_format()` builds a column-index spec by header
  NAME and calls `agent_parser._apply_spec`.
- `modules/agent_parser.py` — `_read_raw_table` (xlsx/csv, auto-separator,
  header-less), `_apply_spec` (the one place every row dict is built),
  `_clean_amount` (strips `$` and `,`, handles `()` negatives, unicode minus),
  `propose_format` (LLM proposes rules for unknown layouts), local Ollama
  categorizer. **Note:** the live `/parse` path calls
  `agent_parser.parse_file_with_agent` (pure-LLM spec per upload), NOT the
  registry `parse_with_format` — the registry is wired in `app.py` (Streamlit).
  The FastAPI path should be migrated to registry-first; currency work assumes
  rows ultimately flow through `_apply_spec`.
- Row schema (one dict): `date, description, amount (neg=spend), category,
  source, included, balance`. Persisted by `modules/database.py`
  `add_transactions`; `transactions` table has no currency column today.
- Frontend: `web/src/pages/Import.tsx` (3-step upload→review→done; editable
  category + include checkbox per row), `web/src/lib/api.ts`
  (`ImportRow`, `parseImport`, `commitImport`). `money.tsx` is hardcoded USD.

**Key gap:** amount is a single signed float with no currency; `_clean_amount`
silently discards the `$` symbol — the one signal we most need.

---

## 2. Currency detection strategy

Detect a currency **per row**, with a **per-file default** fallback. Signals,
highest precedence first (first hit wins; record which one fired as `source`):

1. **Explicit currency column** — header like `Currency`/`Ccy`/`מטבע`. New
   `currency_header` role in the registry; `_col_of` already resolves by name.
   ISO-4217 normalized (`NIS`/`ILS`/`SHEKEL`→`ILS`, `US$`/`USD`→`USD`,
   `EUR`/`€`→`EUR`). Confidence: **explicit**.
2. **Symbol/code in the amount or description cell** — parse `₪`,`$`,`€`,`£`
   and inline ISO codes from the raw amount string *before* `_clean_amount`
   strips them. `$` is ambiguous (USD default, but configurable). Confidence:
   **strong** (symbol) / **explicit** (ISO code).
3. **Registry file-level default** — new `parse.default_currency` per format
   (e.g. a BoA layout ⇒ `USD`; an Israeli bank layout ⇒ `ILS`). Confidence:
   **format-default**.
4. **Statement metadata** — scan preamble rows / filename for an ISO code or
   symbol when no format default. Confidence: **weak**.
5. **Account/person default** — fallback currency configured per person (NEW
   `people.default_currency`, default `ILS` for this household). Confidence:
   **fallback**.
6. **None determinable** — emit `currency=null`, `currency_source="unknown"`,
   add a warning; UI forces the user to pick (§3).

**Mixed-currency statements:** because detection is per-row, a file with a
currency column or per-row symbols just works — each row keeps its own code.
Flag the file in `warnings` ("N currencies detected") so the user notices.

**Precedence/confidence enum** (string, stored as `currency_source`):
`column > cell_symbol/cell_code > format_default > metadata > person_default >
user_override(set in §3) > unknown`. A user override always wins on commit.

---

## 3. User-in-the-loop UX (`Import.tsx`)

- **Upload step:** add a **"Statement currency"** select (Auto-detect / ILS /
  USD / EUR / …). "Auto-detect" = run §2; an explicit pick becomes the
  per-file default, overriding signals 3–5 (never an explicit per-row column,
  which still wins so mixed files stay correct).
- **Review step:** new **Currency column** in the table (`web/src/pages/Import.tsx`
  ~line 162 header list, ~line 168 row map). Show detected code; rows with
  `currency_source==="unknown"` render highlighted and **block commit** until
  resolved. Each cell is an editable `<select>` (per-row override, mirrors the
  existing category `editRow` pattern). A **"Set all to…"** control applies a
  currency to every row at once.
- **Amount display:** `money.tsx` `formatMoney(n)` → `formatMoney(n, currency)`
  so the review table and ledger format per row's code, not hardcoded USD.
- Detection summary line: "Detected ILS for 142 rows; 3 unknown — confirm below."

---

## 4. Data contract (what the importer MUST write per transaction)

Importer is the producer; conversion engine (doc 01) is the consumer. Per row:

| field | type | meaning |
|---|---|---|
| `original_amount` | float | amount in the statement's own currency (signed; neg=spend). **Replaces today's `amount` as the source of truth.** |
| `currency` | str (ISO-4217) \| null | e.g. `ILS`,`USD`. null only if user left it unknown (commit should block this). |
| `currency_source` | str | which signal set it (§2 enum) — for audit/UX, not conversion. |

The importer does **NOT** write converted amounts or touch `fx_rates`; doc 01's
engine derives the converted/base-currency value from `original_amount` +
`currency` + transaction `date`. Keep the existing `amount` column meaning
"native amount" = alias of `original_amount` during migration to avoid breaking
analytics; doc 01 adds the base-currency derived column.

**Touch points to extend (signatures only, no code):**

- `backend/schemas.py`: `ImportRow` += `currency: Optional[str] = None`,
  `currency_source: str = "unknown"`. (`amount` stays.)
- `modules/agent_parser.py::_apply_spec(...)` → emit `currency`,
  `currency_source` in each row dict; add a `_detect_currency(raw_cell,
  desc_cell, spec, file_default) -> (code|None, source)` helper that runs
  BEFORE `_clean_amount` strips symbols.
- `modules/formats.py`: thread new roles `currency_header`,
  `default_currency` into the spec dict built in `parse_with_format`.
- `csv_formats.md`: document `currency_header` + `default_currency`; backfill
  existing formats (`default_currency: "USD"` on the BoA/generic ones).
- `modules/database.py`: `transactions` += `currency TEXT`,
  `currency_source TEXT` (idempotent `ALTER TABLE` in `init_db`, like the
  existing migrations ~lines 214–230); `add_transactions` writes them.
- `web/src/lib/api.ts`: `ImportRow` += `currency`, `currency_source`;
  `Transaction` += `currency`. `commitImport` passes them through.

---

## 5. Edge cases

- **Fees in another currency** (e.g. ILS card with a USD foreign-txn line): per-
  row detection handles it; do not assume one currency per file.
- **Already-converted statements** (statement shows a foreign charge already in
  the home currency): tag the row's *displayed* currency (the home one). Do not
  re-convert. If the statement also lists the original, prefer the home-currency
  column for `original_amount` to avoid double conversion; note in a warning.
- **Rounding:** store `original_amount` exactly as parsed (no rounding at
  import). All rounding is the conversion engine's concern (doc 01).
- **Duplicates:** unchanged — file-hash dedup still applies. Currency is part of
  the row but not the dedup key (dedup is per file, not per row).
- **`$` ambiguity:** default `$`→USD but overridable by file default / person
  default (a household using `$`=ILS-pegged display is unlikely here; ILS uses
  `₪`). Surface as `cell_symbol` confidence so the user can correct.
- **Symbol stripped today:** ensure `_clean_amount` still strips for the numeric
  parse, but detection reads the raw cell first so the symbol isn't lost.

---

## 6. Priority / files

**P0 (unblocks conversion engine):**
- `database.py` migration + `add_transactions` (currency, currency_source).
- `schemas.py` `ImportRow` fields.
- `agent_parser.py` `_detect_currency` + `_apply_spec` emit (signals 1,2,3,5).
- `person_default_currency` (people col + seed `ILS`).

**P1 (correct multi-currency + UX):**
- `formats.py` + `csv_formats.md` new roles; backfill `default_currency`.
- `Import.tsx` review-step Currency column, per-row override, block-on-unknown.
- `api.ts` `ImportRow`/`Transaction`/`commitImport` plumbing.
- `money.tsx` `formatMoney(n, currency)`.

**P2 (polish):**
- Upload-step file-default select + "Set all to…".
- Statement-metadata/filename sniffing (signal 4).
- Migrate FastAPI `/parse` to registry-first (`parse_with_format`) so
  `default_currency` actually applies on the live path.
- Mixed-currency warning summary line.

**Out of scope (doc 01):** `fx_rates` table, date-rate lookup, converted/base
amounts, display-currency conversion in analytics.
