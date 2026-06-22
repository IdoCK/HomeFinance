# Multi-Currency P2 — Coverage + Polish Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
> **Depends on:** P0 (`…-p0-ledger-fx.md`) and P1 (`…-p1-display-toggle.md`).

**Goal:** Make the import flow currency-aware end-to-end (per-row detection surfaced + correctable, file-level default, registry `default_currency`), let users set currency on accounts/budgets/goals, and add maintenance/polish (recompute base, stale-rate badge, currency filter).

**Architecture:** The Import review table gains a Currency column (per-row override + "Set all"), an upload-step source-currency selector that flows to the parser as `file_default`, and **block-on-unknown** before commit. The FastAPI `/parse` path migrates to **registry-first** (`formats.match_format`/`parse_with_format`) so a format's `default_currency` actually applies, falling back to the LLM parser only for unknown layouts. Currency columns gain create/update plumbing on accounts/budgets/goals with symbol-adorned inputs. A "Recompute base values" action re-runs `fx.resolve_rows` over stored rows after a rate refresh.

**Tech Stack:** FastAPI + pydantic v2, `modules/{formats,agent_parser,fx,database}.py`, React + TypeScript, vitest.

## Global Constraints

- **Pivot = USD**, **default display = USD**, **data-minimization** — all from P0/P1, unchanged.
- **Block-on-unknown:** a row whose `currency_source == "unknown"` (or `currency` null) must prevent commit until resolved in the UI.
- **Detection precedence (design §2 / 02-import-detection):** explicit currency column → cell symbol/ISO code → registry `default_currency` → file/upload default → person default (`USD`) → unknown.
- **Import preview shows the row's SOURCE currency**, not the global display toggle (an imported ₪ statement previews in ₪).
- **Registry-first `/parse`:** known formats parse deterministically; the LLM parser remains the fallback for unrecognized files (preserves current behavior for unknown layouts).
- Python tests: `venv/Scripts/python -m pytest <path> -v`. Web tests: `cd web && npm run test`.

---

### Task 1: Registry roles — `currency_header` + `default_currency` threaded into the spec

**Files:**
- Modify: `modules/formats.py:158-174` (`parse_with_format`), `modules/agent_parser.py` (`_apply_spec` currency-column read)
- Modify: `csv_formats.md` (document the two roles; backfill `default_currency` on existing formats)
- Test: `tests/test_formats_currency.py` (create)

**Interfaces:**
- Consumes: `_detect_currency` (P0 Task 6).
- Produces: `parse_with_format` passes `currency_col` (resolved from `currency_header`) and `file_default` (from `parse.default_currency`) into the spec. `_apply_spec` reads an explicit currency column when present (highest precedence), else falls back to `_detect_currency(..., file_default)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_formats_currency.py
import pandas as pd
from modules import agent_parser as ap


def _identity_categorize(desc, rules):
    return "Uncategorized"


def test_explicit_currency_column_wins():
    raw = pd.DataFrame([
        ["Date", "Desc", "Amount", "Ccy"],
        ["2026-03-13", "STORE", "100.00", "ILS"],
    ], dtype=str)
    spec = {"header_row": 0, "data_starts_row": 1, "date_col": 0, "desc_col": 1,
            "amount_col": 2, "currency_col": 3, "file_default": "USD"}
    rows, *_ = ap._apply_spec(raw, spec, "bank", _identity_categorize, [])
    assert rows[0]["currency"] == "ILS"
    assert rows[0]["currency_source"] == "column"


def test_file_default_applies_without_column():
    raw = pd.DataFrame([
        ["Date", "Desc", "Amount"],
        ["2026-03-13", "STORE", "100.00"],
    ], dtype=str)
    spec = {"header_row": 0, "data_starts_row": 1, "date_col": 0, "desc_col": 1,
            "amount_col": 2, "file_default": "ILS"}
    rows, *_ = ap._apply_spec(raw, spec, "bank", _identity_categorize, [])
    assert rows[0]["currency"] == "ILS"
    assert rows[0]["currency_source"] == "file_default"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python -m pytest tests/test_formats_currency.py -v`
Expected: FAIL — `_apply_spec` ignores `currency_col`/`file_default`.

- [ ] **Step 3a: `_apply_spec` reads the column + file_default** (`modules/agent_parser.py`)

In `_apply_spec`, read the new spec keys near the other `spec.get(...)` calls (~line 217):

```python
    currency_col = spec.get("currency_col")
    file_default = spec.get("file_default")
```

Then replace the P0 detection block (the `ccy, ccy_source = _detect_currency(...)` lines) with column-first logic:

```python
        # Currency: an explicit per-row column wins; else detect from the raw
        # cell/symbol, falling back to the file/upload default then person USD.
        if currency_col is not None:
            raw_ccy = "" if pd.isna(r[currency_col]) else str(r[currency_col])
            code = _CODE_CCY.get(raw_ccy.strip().upper())
            if code:
                ccy, ccy_source = code, "column"
            else:
                ccy, ccy_source = _detect_currency(raw_amount_cell, desc_cell, file_default)
        else:
            ccy, ccy_source = _detect_currency(raw_amount_cell, desc_cell, file_default)
```

(`raw_amount_cell` is already computed in P0 Task 6. `_CODE_CCY` is the P0 map.)

- [ ] **Step 3b: `parse_with_format` resolves + threads the roles** (`modules/formats.py`)

In the `spec = {...}` dict (line ~159), add:

```python
        "currency_col": _col_of(hdr_cells, p.get("currency_header")),
        "file_default": p.get("default_currency"),
```

- [ ] **Step 3c: Document + backfill the registry** (`csv_formats.md`)

In the header doc comment (the registry's intro), add to the `parse` role list:

```
    currency_header  : optional column holding an ISO code / symbol per row
    default_currency : the file's currency when no column/symbol is present
                       (e.g. "USD" for a US bank layout, "ILS" for an Israeli one)
```

Then add `"default_currency": "USD"` to the `parse` block of each existing US-bank/Amazon format section.

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python -m pytest tests/test_formats_currency.py -v`
Expected: PASS (both).

- [ ] **Step 5: Regression**

Run: `venv/Scripts/python -m pytest tests/ -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add modules/formats.py modules/agent_parser.py csv_formats.md tests/test_formats_currency.py
git commit -m "feat(import): registry currency_header + default_currency roles"
```

---

### Task 2: `/parse` migrates to registry-first + accepts an upload currency default

**Files:**
- Modify: `backend/api/imports.py:32-44` (`parse`)
- Modify: `modules/agent_parser.py::parse_file_with_agent` (thread `file_default`)
- Test: `tests/api/test_parse_registry.py` (create)

**Interfaces:**
- Consumes: `formats.load_formats`, `formats.match_format`, `formats.parse_with_format`, `agent_parser.parse_file_with_agent`.
- Produces: `POST /import/parse` accepts an extra form field `currency: str = "auto"`. When `"auto"`, `file_default=None`; otherwise it's the upload default passed through. Known formats parse via the registry (so `default_currency` applies); unknown files fall back to the LLM parser. The response `rows` carry `currency`/`currency_source`.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_parse_registry.py
import io


def test_parse_applies_upload_currency_default(client, monkeypatch):
    # Force the LLM-spec path to a deterministic spec so the test is offline.
    from modules import agent_parser as ap
    monkeypatch.setattr(ap, "_call_ollama", lambda *a, **k: {
        "header_row": 0, "data_starts_row": 1, "date_col": 0, "desc_col": 1, "amount_col": 2,
        "spend_is_negative": True})
    monkeypatch.setattr(ap, "categorize_with_agent", lambda *a, **k: {})

    pid = client.get("/api/people").json()[0]["id"]
    csv = b"Date,Desc,Amount\n2026-03-13,STORE,-100.00\n"
    res = client.post("/api/import/parse",
                      files={"file": ("s.csv", io.BytesIO(csv), "text/csv")},
                      data={"source": "bank", "person_id": str(pid), "currency": "ILS"})
    rows = res.json()["rows"]
    assert rows and rows[0]["currency"] == "ILS"
    assert rows[0]["currency_source"] in ("file_default", "cell_symbol", "column")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python -m pytest tests/api/test_parse_registry.py -v`
Expected: FAIL — `parse` has no `currency` field / rows default to USD.

- [ ] **Step 3a: Thread `file_default` through the parser** (`modules/agent_parser.py::parse_file_with_agent`)

```python
def parse_file_with_agent(file_bytes, filename, source, categorize_fn,
                          category_rules, model=DEFAULT_MODEL, file_default=None):
    # ... unchanged until the _apply_spec call ...
    rows, skipped, _ = _apply_spec(raw_df, spec, source, categorize_fn,
                                   category_rules, file_default=file_default)
```

- [ ] **Step 3b: Registry-first `parse`** (`backend/api/imports.py`)

```python
from modules import formats

@router.post("/parse")
def parse(file: UploadFile = File(...), source: str = Form("auto"),
          person_id: int = Form(...), currency: str = Form("auto")):
    raw = file.file.read()
    file_hash = hashlib.sha256(raw).hexdigest()
    if db.get_import(person_id, file_hash):
        return {"already_imported": True, "file_hash": file_hash,
                "filename": file.filename, "source": source, "rows": [], "warnings": []}

    file_default = None if currency == "auto" else currency
    rules = _category_rules(person_id)
    raw_df = agent_parser._read_raw_table(raw, file.filename)
    fmts = formats.load_formats()
    fmt, header_row = formats.match_format(
        raw_df, raw.decode("utf-8-sig", errors="replace"), fmts) if not raw_df.empty else (None, None)

    warnings = []
    if fmt is not None:
        # Registry-first: known layout parses deterministically; default_currency
        # applies. Upload default overrides the registry default when given.
        if file_default:
            fmt = {**fmt, "parse": {**fmt.get("parse", {}), "default_currency": file_default}}
        rows, skipped, _ = formats.parse_with_format(
            raw_df, fmt, header_row, source, parsing.categorize, rules)
        if skipped:
            warnings.append(f"{file.filename}: skipped {skipped} unparseable row(s).")
    else:
        rows, warnings = agent_parser.parse_file_with_agent(
            raw, file.filename, source, parsing.categorize, rules, file_default=file_default)

    unknown = sum(1 for r in rows if r.get("currency_source") == "unknown")
    if unknown:
        warnings.append(f"{file.filename}: {unknown} row(s) need a currency before import.")
    return {"already_imported": False, "file_hash": file_hash,
            "filename": file.filename, "source": source, "rows": rows, "warnings": warnings}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python -m pytest tests/api/test_parse_registry.py -v`
Expected: PASS.

- [ ] **Step 5: Regression**

Run: `venv/Scripts/python -m pytest tests/api/test_imports.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/api/imports.py modules/agent_parser.py tests/api/test_parse_registry.py
git commit -m "feat(import): registry-first /parse + upload currency default"
```

---

### Task 3: Import UI — Currency column, "Set all", upload default, block-on-unknown

**Files:**
- Modify: `web/src/pages/Import.tsx`
- Modify: `web/src/lib/api.ts` (`ImportRow` currency fields; `parseImport` currency arg)
- Test: `web/src/pages/Import.test.tsx` (extend)

**Interfaces:**
- Consumes: P0 `currency`/`currency_source` on rows.
- Produces: an upload-step **Statement currency** select (`Auto-detect / ILS / USD / EUR`), a review-table **Currency** column (per-row `<select>` override), a **"Set all to…"** control, source-currency-aware amount preview, and a commit button **disabled while any row is unknown**.

- [ ] **Step 1: Extend `api.ts`**

```ts
export type ImportRow = {
  date: string; description: string; amount: number; category: string;
  source: string; included: boolean; balance: number | null;
  currency: string; currency_source: string;
};

export async function parseImport(file: File, source: string, personId: number,
                                  currency = "auto"): Promise<ImportParseResult> {
  const fd = new FormData();
  fd.append("file", file); fd.append("source", source);
  fd.append("person_id", String(personId)); fd.append("currency", currency);
  const res = await fetch(`${BASE}/import/parse`, { method: "POST", body: fd });
  if (!res.ok) throw new Error(`POST /import/parse -> ${res.status}`);
  return res.json() as Promise<ImportParseResult>;
}
```

- [ ] **Step 2: Write the failing test** (`web/src/pages/Import.test.tsx`)

```tsx
test("blocks commit while a row currency is unknown", async () => {
  // mock parseImport -> rows: [{...currency: "", currency_source: "unknown"}]
  // advance to review step, then:
  const importBtn = await screen.findByRole("button", { name: /Import 1 transaction/i });
  expect(importBtn).toBeDisabled();
});
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd web && npm run test -- Import`
Expected: FAIL — commit button not disabled on unknown.

- [ ] **Step 4: Edit `Import.tsx`**

Add currency constants + upload state:

```tsx
const CURRENCIES = ["auto", "ILS", "USD", "EUR"];
const symbolFor = (c: string) => (c === "ILS" ? "₪" : c === "EUR" ? "€" : "$");
// in component:
const [uploadCurrency, setUploadCurrency] = useState("auto");
const hasUnknown = rows.some((r) => r.currency_source === "unknown" || !r.currency);
```

Pass the upload currency to parse: `await parseImport(file, source, personId, uploadCurrency);`. Add a select beside the Source select on the upload step:

```tsx
          <div style={{ display: "flex", gap: 8, alignItems: "center", flexWrap: "wrap" }}>
            <label style={h2} htmlFor="import-currency">Statement currency</label>
            <select id="import-currency" value={uploadCurrency}
                    onChange={(e) => setUploadCurrency(e.target.value)} style={pill}>
              {CURRENCIES.map((c) => <option key={c} value={c}>{c === "auto" ? "Auto-detect" : c}</option>)}
            </select>
          </div>
```

In the review table, add a Currency header (between Amount and Category) and make the amount preview source-currency-aware:

```tsx
// header list:
{["Date", "Description", "Amount", "Currency", "Category", "Include"].map(...)}
// amount cell:
<td style={{ ...cell, fontVariantNumeric: "tabular-nums", color: r.amount < 0 ? NEG : POS, fontWeight: 700 }}>
  {r.amount < 0 ? "−" : "+"}{symbolFor(r.currency)}{Math.abs(r.amount).toFixed(2)}
</td>
// new currency cell:
<td style={cell}>
  <select value={r.currency || ""} aria-label={`Currency for ${r.description}`}
          onChange={(e) => editRow(i, { currency: e.target.value, currency_source: "user_override" })}
          style={{ ...pill, padding: "4px 10px",
                   borderColor: r.currency_source === "unknown" || !r.currency ? NEG : undefined }}>
    <option value="">—</option>
    {["ILS", "USD", "EUR"].map((c) => <option key={c} value={c}>{c}</option>)}
  </select>
</td>
```

Add a "Set all to…" control above the table:

```tsx
          <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
            <span style={{ fontSize: 13, color: "var(--fl-muted)" }}>Set all currencies to</span>
            {["ILS", "USD", "EUR"].map((c) => (
              <button key={c} style={pill}
                onClick={() => setRows((rs) => rs.map((r) => ({ ...r, currency: c, currency_source: "user_override" })))}>
                {c}
              </button>
            ))}
          </div>
```

Disable commit on unknown:

```tsx
            <button onClick={doCommit} disabled={busy || hasUnknown}
              style={{ ...primaryBtn, opacity: busy || hasUnknown ? 0.5 : 1,
                       cursor: hasUnknown ? "not-allowed" : "pointer" }}>
              {hasUnknown ? "Set a currency for every row" : busy ? "Importing…" : `Import ${rows.length} transaction${plural(rows.length)}`}
            </button>
```

- [ ] **Step 5: Run test to verify it passes**

Run: `cd web && npm run test -- Import`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add web/src/pages/Import.tsx web/src/lib/api.ts web/src/pages/Import.test.tsx
git commit -m "feat(web): import Currency column, set-all, upload default, block-on-unknown"
```

---

### Task 4: Currency on accounts / budgets / goals (create + update)

**Files:**
- Modify: `backend/schemas.py` (`AccountCreate`, `BudgetUpsert`, `GoalCreate` += `currency`), `modules/database.py` (`add_account`, `set_budget`, `add_goal` persist currency)
- Test: `tests/api/test_entity_currency.py` (create)

**Interfaces:**
- Produces: `AccountCreate`/`BudgetUpsert`/`GoalCreate` accept `currency: str = "USD"`; the DB writers persist it into the P0-added `currency` columns. NetWorth/Budgets/Goals display conversion (P1) already reads each entity's `currency`.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_entity_currency.py
def test_account_stores_currency(client):
    pid = client.get("/api/people").json()[0]["id"]
    client.post("/api/networth/accounts", json={
        "person_id": pid, "name": "TLV Savings", "kind": "savings",
        "is_asset": True, "balance": 1000.0, "currency": "ILS"})
    acc = client.get("/api/networth", params={"person_id": pid}).json()["accounts"][0]
    assert acc["currency"] == "ILS"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python -m pytest tests/api/test_entity_currency.py -v`
Expected: FAIL — `currency` not accepted/persisted (defaults to USD).

- [ ] **Step 3a: Schemas** (`backend/schemas.py`)

Add `currency: str = "USD"` to `AccountCreate`, `BudgetUpsert`, and `GoalCreate`.

- [ ] **Step 3b: DB writers** (`modules/database.py`)

`add_account` — add `currency="USD"` param and include it in the INSERT column list/values:

```python
def add_account(person_id, name, kind, is_asset, balance, currency="USD"):
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO accounts(person_id, name, kind, is_asset, balance, updated_at, currency)
               VALUES (?,?,?,?,?,?,?)""",
            (person_id, name, kind, int(bool(is_asset)), float(balance), now, currency))
        aid = cur.lastrowid
        conn.execute(
            """INSERT INTO balance_snapshots(account_id, date, balance, currency) VALUES (?,?,?,?)
               ON CONFLICT(account_id, date) DO UPDATE SET balance=excluded.balance""",
            (aid, date.today().isoformat(), float(balance), currency))
        return aid
```

`set_budget` — add `currency="USD"`, and set it on both the UPDATE and INSERT branches (append `, currency=?`/extra value). `add_goal` — add `currency="USD"` to the signature and the INSERT.

Then update the two callers to pass it through:
- `backend/api/networth.py::create_account` → `db.add_account(..., body.currency)`.
- `backend/api/budgets.py::upsert_budget` → `db.set_budget(body.person_id, body.category, body.amount, body.currency)`.
- `backend/api/goals.py` create → pass `body.currency`.

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python -m pytest tests/api/test_entity_currency.py -v`
Expected: PASS.

- [ ] **Step 5: Regression**

Run: `venv/Scripts/python -m pytest tests/api/ -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/schemas.py modules/database.py backend/api/networth.py backend/api/budgets.py backend/api/goals.py tests/api/test_entity_currency.py
git commit -m "feat(api): currency on account/budget/goal create + update"
```

---

### Task 5: "Recompute base values" maintenance action

**Files:**
- Create: `backend/api/fx.py` endpoint `POST /fx/recompute` (add to the P1 router)
- Modify: `modules/database.py` (add `recompute_amount_base`)
- Test: `tests/api/test_fx_recompute.py` (create)

**Interfaces:**
- Consumes: `fx.resolve_rows`, the stored `transactions`.
- Produces: `database.recompute_amount_base()` re-derives `amount_base` for every transaction from its stored `amount`/`currency`/`date` (USD passthrough; non-USD via cached/fetched rate), writing the result back. `POST /fx/recompute` returns `{ updated: int, stale: int }`.

- [ ] **Step 1: Write the failing test**

```python
# tests/api/test_fx_recompute.py
def test_recompute_fills_base_after_rate_added(client, monkeypatch):
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json",
                        lambda url: (_ for _ in ()).throw(OSError("offline")))
    pid = client.get("/api/people").json()[0]["id"]
    # Commit an ILS row while offline -> amount_base unresolved (None).
    client.post("/api/import/commit", json={
        "person_id": pid, "filename": "f.csv", "file_hash": "h", "source": "bank",
        "rows": [{"date": "2026-03-13", "description": "TLV", "amount": 400.0, "currency": "ILS"}]})
    # Provide the rate, then recompute.
    fx.upsert_rate("2026-03-13", "USD", "ILS", 4.0)
    out = client.post("/api/fx/recompute").json()
    assert out["updated"] >= 1 and out["stale"] == 0
    row = next(t for t in client.get("/api/transactions", params={"person_id": pid}).json()
               if t["description"] == "TLV")
    assert row["amount_base"] == 100.0   # 400 ILS / 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `venv/Scripts/python -m pytest tests/api/test_fx_recompute.py -v`
Expected: FAIL — `404` (no `/fx/recompute`).

- [ ] **Step 3a: DB recompute** (`modules/database.py`)

```python
def recompute_amount_base():
    """Re-derive amount_base (USD) for every transaction from its stored
    amount/currency/date. Returns (updated, stale). Used after a rate refresh."""
    from modules import fx
    with get_conn() as conn:
        rows = [dict(r) for r in conn.execute(
            "SELECT id, amount, currency, date FROM transactions")]
        fx.resolve_rows(rows)  # fills amount_base / sets rate_stale
        updated = stale = 0
        for r in rows:
            if r.get("rate_stale"):
                stale += 1
                continue
            conn.execute("UPDATE transactions SET amount_base=? WHERE id=?",
                         (r["amount_base"], r["id"]))
            updated += 1
    return updated, stale
```

- [ ] **Step 3b: Endpoint** (`backend/api/fx.py`)

```python
@router.post("/recompute")
def recompute():
    updated, stale = db.recompute_amount_base()
    return {"updated": updated, "stale": stale}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `venv/Scripts/python -m pytest tests/api/test_fx_recompute.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/api/fx.py modules/database.py tests/api/test_fx_recompute.py
git commit -m "feat(fx): recompute amount_base maintenance action"
```

---

### Task 6: Polish — stale-rate badge + transactions currency filter

**Files:**
- Modify: `web/src/components/money.tsx` (stale affordance), `web/src/pages/Transactions.tsx` (currency filter)
- Test: `web/src/components/money.test.tsx` (extend)

**Interfaces:**
- Consumes: P1 `rate_stale` on transactions, currency-aware `Money`.
- Produces: `Money` gains `rateMissing?: boolean` → renders a muted `(no rate)` info affordance instead of a misleading number color. Transactions gains an "entered in" currency facet (`All / ₪ / $`) filtering by `original_currency`.

- [ ] **Step 1: Extend the money test**

```tsx
test("Money flags a missing rate with a muted affordance", () => {
  wrap(<Money value={400} rateMissing />);
  expect(screen.getByText(/no rate/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd web && npm run test -- money`
Expected: FAIL — no "no rate" text.

- [ ] **Step 3a: `Money` stale affordance** (`web/src/components/money.tsx`)

Add `rateMissing?: boolean` to the props and render, after the value:

```tsx
      {rateMissing && (
        <span title="No exchange rate for this date — showing the original amount"
              style={{ color: "var(--fl-muted)", fontSize: "0.78em", marginLeft: 4 }}>
          (no rate)
        </span>
      )}
```

- [ ] **Step 3b: Transactions currency facet** (`web/src/pages/Transactions.tsx`)

Add `const [ccyFilter, setCcyFilter] = useState<string>("all");`, a select in the filter bar:

```tsx
          <select value={ccyFilter} onChange={(e) => setCcyFilter(e.target.value)} style={pill}>
            <option value="all">Any currency</option>
            <option value="ILS">₪ entered</option>
            <option value="USD">$ entered</option>
          </select>
```

and extend the `rows` filter with `(ccyFilter === "all" || t.original_currency === ccyFilter)` (add `ccyFilter` to that memo's deps). Pass `rateMissing={t.rate_stale}` to the Amount column's `<Money>`.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd web && npm run test -- money` then `npm run test -- Transactions`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add web/src/components/money.tsx web/src/pages/Transactions.tsx web/src/components/money.test.tsx
git commit -m "feat(web): stale-rate badge + transactions currency filter"
```

---

## Self-Review

**Spec coverage (design §10 P2; 02-import-detection P1/P2; 03-frontend P2):**
- Registry `currency_header` + `default_currency` → Task 1. ✔
- Registry-first `/parse` + upload default → Task 2. ✔
- Import review Currency column, set-all, block-on-unknown, source-currency preview → Task 3. ✔
- Currency on accounts/budgets/goals create+update → Task 4. ✔
- "Recompute base values" → Task 5. ✔
- Stale-rate badge + currency filter facet → Task 6. ✔

**Deliberately out of P2 scope:** EUR as a *display* target (toggle stays ₪/$ per the locked decision — EUR can be *stored/entered* via Tasks 3/4 but isn't a display option); per-card "in ₪" micro-labels and full input symbol adornments beyond the import preview (cosmetic, deferred).

**Placeholder scan:** no `TODO`/`TBD`. The page-edit steps name exact handlers, props, state, and the JSX insertion points; the new backend code is fully shown.

**Type consistency:** `currency`/`currency_source` on `ImportRow` (Task 3) match the P0 row dict and `_apply_spec` output (Task 1). `currency` on `AccountCreate`/`BudgetUpsert`/`GoalCreate` (Task 4) matches the P0 columns and the P1 display readers. `recompute_amount_base` returns `(updated, stale)` consumed verbatim by `POST /fx/recompute` (Task 5). `rateMissing` (Task 6) aligns with `rate_stale` from P1 Task 2.
