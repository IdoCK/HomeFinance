# CSV Format Registry

Known statement/export layouts. When you upload a file, the app finds the
**first best-matching** format below, then parses it deterministically with that
format's rules. You can edit these by hand, or add new ones from the **Import**
tab ("Add new file type") when a file matches nothing here.

Each format is one `## Identifier` heading followed by a ```json block:

- **match** — how the file is recognized
  - `header_signature`: header names that must all appear together in one row.
  - `file_contains`: optional strings that must appear somewhere in the file.
- **parse** — how the file is read (columns referenced by header name)
  - `*_header`: which header holds the date / description / amount / debit / credit.
  - `amount_already_signed`: the amount column already uses +/- for in/out.
  - `spend_is_negative`: when not already signed, is money-out negative?
  - `date_format`: Python strptime format, or null to auto-detect.
  - `balance_header`: optional — the running-balance column. When set, the
    latest-dated row's balance is offered on import to refresh an account
    balance (Net Worth). Omit it on feeds without a running balance (cards).
  - `skip_summary_rows`: drop aggregate rows like "Total credits"/"Ending balance".
  - `currency_header`: optional column holding an ISO code / symbol per row.
  - `default_currency`: the file's currency when no column/symbol is present
    (e.g. "USD" for a US bank layout, "ILS" for an Israeli one).
  - `exclude_keywords`: optional list of substrings (case-insensitive) marking
    internal transfers such as credit-card bill payments. Matching rows are kept
    but flagged as **excluded from calculations** (shown dimmed; the user can
    re-include any row). They're neither spend nor income and would otherwise
    double-count against the matching row on the other account's statement.

---

## Bank of America — Bank Statement

```json
{
  "source": "bank",
  "match": {
    "header_signature": ["Date", "Description", "Amount", "Running Bal."],
    "file_contains": ["Total credits", "Total debits"]
  },
  "parse": {
    "date_header": "Date",
    "desc_header": "Description",
    "amount_header": "Amount",
    "debit_header": null,
    "credit_header": null,
    "balance_header": "Running Bal.",
    "amount_already_signed": true,
    "spend_is_negative": true,
    "date_format": "%m/%d/%Y",
    "skip_summary_rows": true,
    "default_currency": "USD",
    "exclude_keywords": ["payment to crd", "payment to acct"]
  }
}
```

## Generic Credit Card — Signed Amount

```json
{
  "source": "credit_card",
  "match": {
    "header_signature": ["Date", "Description", "Amount"],
    "file_contains": []
  },
  "parse": {
    "date_header": "Date",
    "desc_header": "Description",
    "amount_header": "Amount",
    "debit_header": null,
    "credit_header": null,
    "amount_already_signed": true,
    "spend_is_negative": true,
    "date_format": null,
    "skip_summary_rows": true,
    "default_currency": "USD"
  }
}
```

## Bank of America — Credit Card (Posted Date / Payee)

```json
{
  "source": "credit_card",
  "match": {
    "header_signature": ["Posted Date", "Payee", "Amount"],
    "file_contains": []
  },
  "parse": {
    "date_header": "Posted Date",
    "desc_header": "Payee",
    "amount_header": "Amount",
    "debit_header": null,
    "credit_header": null,
    "amount_already_signed": true,
    "spend_is_negative": true,
    "date_format": "%m/%d/%Y",
    "skip_summary_rows": true,
    "default_currency": "USD",
    "exclude_keywords": ["payment from chk", "mobile recurring from chk"]
  }
}
```

## Discount Bank of Israel — Bank Statement

```json
{
  "source": "bank",
  "match": {
    "header_signature": ["Date", "Value date", "Description", "Channel"],
    "file_contains": []
  },
  "parse": {
    "date_header": "Date",
    "desc_header": "Description",
    "amount_header": "₪ Credit/Debit",
    "debit_header": null,
    "credit_header": null,
    "balance_header": "₪ NIS Balance",
    "amount_already_signed": true,
    "spend_is_negative": true,
    "date_format": null,
    "skip_summary_rows": true,
    "default_currency": "ILS"
  }
}
```

## Discount Bank of Israel — Visa Credit Card (Cal)

```json
{
  "source": "credit_card",
  "match": {
    "header_signature": ["Business", "Date of transaction", "Amount to be charged", "Date of charge"],
    "file_contains": []
  },
  "parse": {
    "date_header": "Date of transaction",
    "desc_header": "Business",
    "amount_header": "Amount to be charged",
    "debit_header": null,
    "credit_header": null,
    "amount_already_signed": false,
    "spend_is_negative": false,
    "date_format": "%d/%m/%Y",
    "skip_summary_rows": true,
    "default_currency": "ILS"
  }
}
```

## Discount Bank of Israel — Visa Credit Card (Cal, Hebrew)

```json
{
  "source": "credit_card",
  "match": {
    "header_signature": ["כרטיס", "בית עסק", "תאריך עסקה", "סכום החיוב", "תאריך החיוב"],
    "file_contains": []
  },
  "parse": {
    "date_header": "תאריך עסקה",
    "desc_header": "בית עסק",
    "amount_header": "סכום החיוב",
    "debit_header": null,
    "credit_header": null,
    "amount_already_signed": false,
    "spend_is_negative": false,
    "date_format": "%d/%m/%Y",
    "skip_summary_rows": true,
    "default_currency": "ILS"
  }
}
```

## Isracard Mastercard — Transaction Detail (Hebrew)

```json
{
  "source": "credit_card",
  "match": {
    "header_signature": ["תאריך רכישה", "שם בית עסק", "סכום חיוב", "מטבע חיוב"],
    "file_contains": []
  },
  "parse": {
    "date_header": "תאריך רכישה",
    "desc_header": "שם בית עסק",
    "amount_header": "סכום חיוב",
    "debit_header": null,
    "credit_header": null,
    "amount_already_signed": false,
    "spend_is_negative": false,
    "date_format": "%d.%m.%y",
    "skip_summary_rows": true,
    "default_currency": "ILS"
  }
}
```

## Amazon — Order Items Export

```json
{
  "source": "amazon",
  "match": {
    "header_signature": ["Order Date", "Title", "Item Total"],
    "file_contains": []
  },
  "parse": {
    "date_header": "Order Date",
    "desc_header": "Title",
    "amount_header": "Item Total",
    "debit_header": null,
    "credit_header": null,
    "amount_already_signed": false,
    "spend_is_negative": false,
    "date_format": null,
    "skip_summary_rows": true,
    "default_currency": "USD"
  }
}
```
