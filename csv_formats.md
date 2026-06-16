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
  - `skip_summary_rows`: drop aggregate rows like "Total credits"/"Ending balance".

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
    "amount_already_signed": true,
    "spend_is_negative": true,
    "date_format": "%m/%d/%Y",
    "skip_summary_rows": true
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
    "skip_summary_rows": true
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
    "skip_summary_rows": true
  }
}
```
