# Credit-Card Bill Reconciliation — Design

**Date:** 2026-06-30
**Status:** Approved (design)

## Problem

When a user imports both a **credit-card statement** and the **bank statement** that
pays it, the card spending is counted twice:

1. Once as the individual **card line items** (e.g. the Isracard transactions,
   including BIT/PayBox charges funded by the card).
2. Once as the single lump **bank debit** that pays the monthly card bill
   (e.g. Discount Bank `DIRECT DEBIT −12,439.16`).

This is confirmed in real data: the Isracard March statement's line items sum to
exactly **₪12,439.16**, which equals one `DIRECT DEBIT` row on the Discount Bank
statement.

A keyword rule (e.g. excluding `DIRECT DEBIT`) is **not** viable: that description
is generic and shared with legitimate, non-duplicated debits (mortgage, utilities).
The card-bill row is only distinguishable by **amount equality with an imported
card statement's total** — a cross-file signal.

## Goal

Detect, across imported files, the bank debit that pays an imported card
statement, and let the user exclude that bank lump from totals with one click —
keeping the itemized card spend (with merchant detail and categories) as the
single, correct record of the spending.

Out of scope: auto-exclusion; touching the card line items; changing how
BIT/PayBox individual charges are counted (they remain normal spend, counted once
on the card).

## Approach

Mirror the existing **transfer-pair** model (`analytics.find_transfer_pairs` →
`GET /transactions/transfers` → UI panel → exclude via `PATCH
/transactions/{id}` `included=0`). The same detect → surface → one-click-exclude
flow, non-destructive and reversible. No new write path; reuse the `included`
flag (analytics already filters `included != 0`).

The card-bill case differs in shape from a transfer pair: it matches **one bank
outflow ↔ the sum of many card line items** (all on the spend side), not one
outflow ↔ one inflow. So it gets its own detector rather than extending
`find_transfer_pairs`.

## Components

### 1. `analytics.find_card_bill_payments(txns, *, days=45)`

A pure function (no DB) in `modules/analytics.py`, styled after
`find_transfer_pairs`.

**Algorithm:**

- Group `source == "credit_card"` transactions by `file_hash` → one group per
  imported card statement. Skip rows with no `file_hash` (legacy/manual: cannot
  be attributed to a statement).
- For each statement group, compute `total = abs(sum(amount_base))` (USD pivot;
  fall back to raw `amount` when `amount_base` is absent, like
  `find_transfer_pairs`).
- Collect `source == "bank"` outflows (`amount < 0`), keyed by `abs(amount_base)`.
- **Match** a bank outflow to a statement total when:
  - their USD-base amounts are equal within tolerance `0.02`, **and**
  - the bank date is **within `days` (default 45) after the statement's latest
    charge date** — `latest_card_date <= bank_date <= latest_card_date + days`.
    (Amount equality against a full statement total is a near-unique signal; the
    window is a guardrail against a coincidental same-amount debit in another
    period.)
- **Greedy**, largest total first; each bank row and each card statement used at
  most once.

**Returns** a list (largest amount first) of dicts:

| field | meaning |
|---|---|
| `amount` | matched amount, USD base |
| `bank_id` | the bank transaction id (the row to exclude) |
| `card_file_hash` | file_hash of the matched card statement |
| `bank_date` | date of the bank debit |
| `bank_amount` | the bank leg's original amount (its own currency) |
| `bank_currency` | the bank leg's original currency |
| `card_txn_count` | number of line items in the matched statement |
| `card_date_range` | `[earliest, latest]` charge dates of the statement |
| `bank_included` | current `included` state of the bank row (so the UI can show "already excluded") |

### 2. `GET /transactions/card-bills`

In `backend/api/transactions.py`, mirroring `/transfers`:

- Pull `db.get_transactions(person_id)`, run `find_card_bill_payments(...)`.
- Attach each match's card statement `filename` using the same
  `(person_id, file_hash) → filename` map that `list_transactions` builds from
  `db.list_imports`, so the UI can name the statement.
- person_id omitted = household scope; a person scope restricts to that person.

Exclusion uses the **existing** `PATCH /transactions/{txn_id}` with
`included=0` — no new endpoint.

### 3. Frontend

- `web/src/lib/api.ts`: a `CardBillPayment` type and
  `getCardBillPayments(personId?)` → `GET /transactions/card-bills`.
- `web/src/pages/Transactions.tsx`: a **"Card bill payments"** panel beside the
  transfers panel. Each detected match shows the bank lump (amount, date) and the
  card statement it pays (filename, line-item count, date range), with a
  one-click **Exclude bill payment** that `PATCH`es the bank row `included=0`.
  Rows already excluded show as such with an **Include** toggle (reversible).

## Data flow

1. User imports card statement(s) and the bank statement (existing flow; file-hash
   dedup unchanged). Rows stored with `file_hash`, `source`, `amount_base`.
2. Transactions page calls `/transactions/card-bills` → renders detected matches.
3. User clicks **Exclude bill payment** → `PATCH` bank row `included=0` → it drops
   from spend totals (analytics filters `included != 0`).

## Edge cases

- **Only bank imported** (no card) → no statement total to match → debit counts
  (correct; the lump is the only record).
- **Only card imported** (no bank) → no bank lump → line items count once
  (correct).
- **Two cards → two bank debits** → two independent matches, each row used once.
- **Card rows without `file_hash`** (legacy/manual) → skipped, no detection.
- **Bank debit equals a single card *line item*** (not the statement total) → no
  match (we match totals only).
- **Currency safety** — match on `amount_base` (USD): a ₪ total won't match a $
  debit with the same raw number.
- **Interest/fees or multi-card bundling on the bank debit** → totals won't match
  exactly → not flagged (degrades to "not detected", never to a wrong exclusion).

## Error handling

- Missing `amount_base` → fall back to raw `amount` (matches `find_transfer_pairs`).
- No card imports / empty groups → empty result.

## Testing

New `tests/test_card_bills.py` mirroring `tests/test_transfers.py`:

- Bank debit equals one statement total → one match.
- Two cards, two bank debits → two matches, each row used once.
- Equal amount but bank date outside the 45-day window → no match.
- Card rows lacking `file_hash` → no match.
- Already-excluded bank row → reported with `bank_included = False`.
- Bank debit equal to a single card line (not the total) → no match.
- Currency safety: ₪ total vs $ debit, equal raw numbers, different base → no match.

API test in the existing transactions API test module for
`GET /transactions/card-bills` (shape + filename attachment).

Frontend: `web/src/lib/api.test.ts` for `getCardBillPayments` URL building;
`web/src/pages/Transactions.test.tsx` for the panel rendering a match and the
exclude action calling `updateTransaction(included=0)`.
