# HomeFinance Multi-Currency — Implementation Plan

**Goal:** users enter statements in **any** currency; the system converts using the rate **on each transaction's date**; users toggle the display between **₪ ILS** and **$ USD**; import **detects** the currency from statements where possible. All while staying **local-first — nothing leaves the device** unless the user explicitly asks.

Master synthesis. Detailed analysis in the section docs:
- [`01-datamodel-fx.md`](01-datamodel-fx.md) — schema, conversion engine, rate sourcing, migration
- [`02-import-detection.md`](02-import-detection.md) — currency detection in the import pipeline
- [`03-frontend-ux.md`](03-frontend-ux.md) — display-currency toggle, `money.tsx`, per-surface UX

---

## 1. Architecture in one picture

```
Import (detect currency) ──► transactions{ original_amount, currency, currency_source, amount_base }
                                                  │ write-time conversion via modules/fx.py
                              fx_rates(rate_date, base=ILS, quote, rate)  ◄── bundled BOI seed CSV
                                                  │                            + opt-in "Refresh rates"
Analytics read amount_base (canonical ILS) ──► API ──► UI converts base→display (ILS|USD) at the edge
```

- **Canonical base = ILS.** Every transaction stores its *original* amount + currency **and** a derived `amount_base` (ILS), computed once at write-time (a transaction's date never changes). Analytics keep working unchanged by reading `amount_base`.
- **Display** (ILS↔USD toggle) is a **query-time / render-edge** conversion using *today's* rate for "current" aggregates, while each ledger row stays pinned to its transaction-day rate. **Sum first, round last.**

## 2. The crux — FX rates without breaking local-first

Live FX API calls would violate "nothing leaves this device." Decision:
- **Ship a bundled offline historical-rates seed** (`data/fx_seed.csv`, Bank-of-Israel daily reference rates) → zero network by default.
- **Explicit opt-in "Refresh rates"** action the user triggers to fetch recent days (the only outbound call, clearly user-initiated).
- **Manual entry** as a gap-filler for missing days.
- Rate lookup rule: `WHERE rate_date <= ? ORDER BY rate_date DESC LIMIT 1` (exact day, else nearest prior business day); earliest-rate fallback flagged `rate_stale`.

## 3. Locked decisions

| Area | Decision | Source |
|---|---|---|
| Canonical base | **ILS**, stored as `amount_base` per transaction | datamodel |
| Default display | **ILS** (current USD default is wrong for an Israeli household) | frontend |
| `fx_rates` table | `(rate_date, base, quote, rate, source, fetched_at)`, PK `(rate_date,base,quote)`, store base=ILS & invert in code | datamodel |
| Conversion time | original→base at **write-time**; base→display at **render edge** | datamodel/frontend |
| Toggle scope | **household-wide**, single control (not per-person) | datamodel/frontend |
| Toggle home | top-bar segmented pill `₪ ILS \| $ USD`; default + FX inspection in Settings; state in new `web/src/lib/currency.tsx` (modeled on `theme.tsx`, localStorage `hf-currency`) | frontend |
| Import contract | importer writes `original_amount`, `currency` (ISO-4217), `currency_source`; **never converts** | import |
| Net Worth / reconciliation | shown in **native currency** to avoid FX-rounding false discrepancies | frontend |
| New files | `modules/fx.py`, `data/fx_seed.csv`, `backend/api/fx.py`, `web/src/lib/currency.tsx` | all |

## 4. Import currency detection

Current flow: `Import.tsx` → `parseImport` → `POST /import/parse` (`backend/api/imports.py`) → `agent_parser.parse_file_with_agent` → `/import/commit` → `db.add_transactions`. Rows carry no currency; `_clean_amount` strips `$`/`,` (discarding the symbol we need).

- **Detection precedence:** explicit currency column → cell symbol/ISO code → registry `default_currency` → statement metadata → person default → **unknown**.
- Per-row detection supports **mixed-currency files**; **unknown blocks commit** until resolved.
- **UX:** file-level currency select on upload; a **Currency column** in the review table with per-row override + "Set all"; unknowns highlighted.
- ⚠️ **Finding:** the FastAPI `/parse` path uses the pure-LLM parser, not the header registry, so registry `default_currency` only helps after `/parse` is migrated to registry-first (**P2**).

## 5. Phased sequence

- **P0 — Ledger + FX core.** Schema: add `currency`,`currency_source`,`amount_base` to `transactions`; create `fx_rates`; build `modules/fx.py` (lookup + convert); ship `data/fx_seed.csv` seed loader. Migration backfills existing rows (see open Q2).
- **P1 — Display + toggle.** `backend/api/fx.py` (`/fx` router); `CurrencyProvider` + currency-aware `money.tsx`; top-bar toggle; re-express Overview/Budgets/Recurring/Goals; "Refresh rates" action.
- **P2 — Import detection + spread.** Currency detection in the import pipeline + review-table UX; migrate `/parse` to registry-first; account/goal/snapshot currency; Net-Worth native display; recompute-`amount_base` maintenance action.

## 6. Open questions (need your call)

1. **Canonical base = ILS, default display = ILS?** (recommended — Israeli household).
2. **What currency is the *existing* `data/finance.db` (~150 rows) in?** This drives the migration backfill. The datamodel agent assumed **USD** (the seeded taxonomy is US-shaped) but flagged it as a guess — please confirm USD vs ILS.
3. **Rate sourcing OK?** Bundled BOI historical CSV + opt-in "Refresh rates" + manual entry — preserves local-first. Approve, or prefer manual-only?
4. **How deep should the bundled rate history go?** (e.g. back to the earliest transaction date you'll import.)

---
*Generated from three parallel specialist analyses (data model/FX, import detection, frontend UX). Planning only — no source files were modified.*
