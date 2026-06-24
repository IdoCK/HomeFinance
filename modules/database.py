"""SQLite storage for the household finance dashboard.

All data lives in a single local file (data/finance.db). Nothing leaves the
machine except the anonymized summaries sent for AI insights (see ai_insights.py).
"""

import json
import sqlite3
from datetime import datetime, date
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).resolve().parent.parent / "data" / "finance.db"

# Starter taxonomy seeded for a person with no categories yet. Income categories
# come first so money-in is differentiated (salary vs reimbursement vs rewards)
# instead of collapsing into a single bucket.
_STARTER_CATEGORIES = [
    ("Salary", "payroll, direct dep, salary, des:payroll"),
    ("Reimbursement", "zelle payment from, venmo from, reimburs"),
    ("Rewards & Interest", "cashreward, cash back, cash rewards, rewards, interest"),
    ("Groceries", "whole foods, trader joe, key food, grocery, safeway, costco"),
    ("Eating Out", "restaurant, cafe, coffee, grubhub, doordash, uber eats, bakery, bar"),
    ("Transit", "mta, uber, lyft, path, transit, parking, nyct, ferry"),
    ("Shopping", "amazon, target, walmart, best buy, store"),
    ("Subscriptions", "apple.com/bill, netflix, spotify, hulu, verizon, at&t"),
    ("Health & Fitness", "pharmacy, cvs, walgreens, gym, nysc, fitness, dental, doctor"),
    ("Housing", "rent, mortgage, clickpay, proprtypay, hoa"),
]

# Starter vendor groups: collapse merchant-name variants into one bucket in the
# Analysis drill-down. Seeded for a person with no vendors yet; fully editable.
_STARTER_VENDORS = [
    ("Amazon", "amazon, amzn"),
    ("MTA", "mta, nyct"),
    ("PATH", "path tapp"),
    ("NYSC", "nysc"),
    ("Uber", "uber"),
    ("Lyft", "lyft"),
    ("Whole Foods", "whole foods"),
    ("Apple", "apple.com"),
    ("Verizon", "verizon"),
    ("Grubhub", "grubhub"),
    ("Venmo", "venmo"),
    ("Zelle", "zelle"),
]


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    """Create tables if they don't exist and seed the two household members."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with get_conn() as conn:
        c = conn.cursor()
        c.executescript(
            """
            CREATE TABLE IF NOT EXISTS people (
                id   INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL
            );

            CREATE TABLE IF NOT EXISTS categories (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL,
                name      TEXT NOT NULL,
                -- simple keyword rules: comma-separated substrings matched
                -- (case-insensitive) against a transaction description
                keywords  TEXT DEFAULT '',
                UNIQUE(person_id, name),
                FOREIGN KEY(person_id) REFERENCES people(id)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id   INTEGER NOT NULL,
                date        TEXT NOT NULL,          -- ISO YYYY-MM-DD
                description TEXT NOT NULL,
                amount      REAL NOT NULL,          -- negative = spend, positive = income
                category    TEXT DEFAULT 'Uncategorized',
                source      TEXT DEFAULT '',        -- e.g. 'amazon', 'credit_card', 'bank'
                included    INTEGER NOT NULL DEFAULT 1,  -- 0 = excluded from all calculations
                balance     REAL,                    -- running balance from the statement, if any
                FOREIGN KEY(person_id) REFERENCES people(id)
            );

            CREATE TABLE IF NOT EXISTS imported_files (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id   INTEGER NOT NULL,
                file_hash   TEXT NOT NULL,           -- sha256 of the file bytes
                filename    TEXT NOT NULL,
                count       INTEGER NOT NULL,        -- transactions imported
                imported_at TEXT NOT NULL,           -- ISO timestamp
                UNIQUE(person_id, file_hash),
                FOREIGN KEY(person_id) REFERENCES people(id)
            );

            CREATE TABLE IF NOT EXISTS goals (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id    INTEGER,               -- NULL = household/shared goal
                name         TEXT NOT NULL,
                target_amount REAL NOT NULL,
                saved_amount  REAL DEFAULT 0,
                target_date   TEXT,                 -- ISO YYYY-MM-DD
                horizon       TEXT DEFAULT 'short',  -- 'short' or 'long'
                notes         TEXT DEFAULT ''
            );

            -- Net-worth ledger (Wave 2). Decoupled from transactions: an account's
            -- balance is a POSITIVE magnitude; is_asset decides whether it adds to
            -- or subtracts from net worth, never the sign of balance.
            CREATE TABLE IF NOT EXISTS accounts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id   INTEGER,               -- NULL = shared/household
                name        TEXT NOT NULL,
                kind        TEXT NOT NULL,          -- checking|savings|credit_card|investment|property|loan|other
                is_asset    INTEGER NOT NULL,       -- 1 = asset, 0 = liability
                balance     REAL NOT NULL DEFAULT 0,
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS balance_snapshots (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                account_id  INTEGER NOT NULL,
                date        TEXT NOT NULL,          -- ISO YYYY-MM-DD
                balance     REAL NOT NULL,          -- positive magnitude, like accounts.balance
                UNIQUE(account_id, date)            -- one snapshot per account per day (upsert)
            );

            -- Per-category monthly spending budget (Wave 3). person_id NULL =
            -- household budget. `category` matches a category (or parent) name.
            CREATE TABLE IF NOT EXISTS budgets (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER,
                category  TEXT NOT NULL,
                amount    REAL NOT NULL              -- monthly cap, positive
            );

            -- Vendor groups: collapse merchant-name variants (Amazon.com,
            -- AMAZON MKTPL, AMAZON PRIME → "Amazon") into one bucket in the
            -- Analysis drill-down. Same keyword-rule shape as categories.
            CREATE TABLE IF NOT EXISTS vendors (
                id        INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL,
                name      TEXT NOT NULL,
                keywords  TEXT DEFAULT '',
                UNIQUE(person_id, name),
                FOREIGN KEY(person_id) REFERENCES people(id)
            );

            -- User-defined events to slice spending by (Analysis filter). person_id
            -- NULL = household. kind: 'window' (start_date..end_date, e.g. a trip),
            -- 'recurring' (rule JSON of dow / day_of_month / month_day, e.g. paydays,
            -- birthdays), or 'tagged' (membership only via transaction_tags).
            CREATE TABLE IF NOT EXISTS events (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id  INTEGER,
                name       TEXT NOT NULL,
                kind       TEXT NOT NULL,
                start_date TEXT,
                end_date   TEXT,
                rule       TEXT,
                FOREIGN KEY(person_id) REFERENCES people(id)
            );

            -- Explicit membership of a transaction in an event (unions with the
            -- event's date predicate, so you can add stragglers outside a window).
            CREATE TABLE IF NOT EXISTS transaction_tags (
                transaction_id INTEGER NOT NULL,
                event_id       INTEGER NOT NULL,
                UNIQUE(transaction_id, event_id),
                FOREIGN KEY(transaction_id) REFERENCES transactions(id),
                FOREIGN KEY(event_id) REFERENCES events(id)
            );
            """
        )
        # Migration: rename the legacy default member names (pre-2026-06 DBs
        # seeded "You"/"Spouse") to the household's names. Idempotent and only
        # touches rows still at the old defaults, so user-chosen names are never
        # clobbered. Must run BEFORE the seed below so the INSERT OR IGNORE
        # collides on the new (now-existing) names instead of adding two more
        # people. Guarded by NOT EXISTS so a DB that already carries the
        # canonical name (plus a stray legacy row from a re-seed) doesn't hit a
        # UNIQUE(name) collision on upgrade — the stray is simply left in place.
        c.execute("UPDATE people SET name='Ido' WHERE name='You' "
                  "AND NOT EXISTS (SELECT 1 FROM people WHERE name='Ido')")
        c.execute("UPDATE people SET name='Aviv' WHERE name='Spouse' "
                  "AND NOT EXISTS (SELECT 1 FROM people WHERE name='Aviv')")
        # Seed the two members once.
        for name in ("Ido", "Aviv"):
            c.execute("INSERT OR IGNORE INTO people(name) VALUES (?)", (name,))

        # Seed a starter category taxonomy for any person who has none yet, so
        # income isn't one undifferentiated bucket and first imports auto-tag.
        # Only seeds when empty, so it never clobbers the user's edits.
        for (person_id,) in c.execute("SELECT id FROM people").fetchall():
            has = c.execute(
                "SELECT COUNT(*) FROM categories WHERE person_id=?", (person_id,)
            ).fetchone()[0]
            if not has:
                for name, kws in _STARTER_CATEGORIES:
                    c.execute(
                        "INSERT OR IGNORE INTO categories(person_id, name, keywords) "
                        "VALUES (?,?,?)", (person_id, name, kws))
            # Seed starter vendor groups for a person who has none yet.
            has_v = c.execute(
                "SELECT COUNT(*) FROM vendors WHERE person_id=?",
                (person_id,)).fetchone()[0]
            if not has_v:
                for name, kws in _STARTER_VENDORS:
                    c.execute(
                        "INSERT OR IGNORE INTO vendors(person_id, name, keywords) "
                        "VALUES (?,?,?)", (person_id, name, kws))

        # Migration: link each transaction to the file it was imported from
        # (added after the first releases, so older DBs lack the column).
        cols = [r[1] for r in c.execute("PRAGMA table_info(transactions)")]
        if "file_hash" not in cols:
            c.execute("ALTER TABLE transactions ADD COLUMN file_hash TEXT")
        # Migration: per-row "counts toward calculations" flag. Detected internal
        # transfers (e.g. credit-card payments) are stored with included=0; older
        # rows default to 1 so existing totals are unchanged.
        if "included" not in cols:
            c.execute(
                "ALTER TABLE transactions ADD COLUMN included INTEGER NOT NULL DEFAULT 1"
            )
        # Migration: optional parent (rollup group) for categories.
        cat_cols = [r[1] for r in c.execute("PRAGMA table_info(categories)")]
        if "parent" not in cat_cols:
            c.execute("ALTER TABLE categories ADD COLUMN parent TEXT DEFAULT ''")
        # Migration: per-row running balance (for month-end balance history).
        if "balance" not in cols:
            c.execute("ALTER TABLE transactions ADD COLUMN balance REAL")

        # Migration: multi-currency. `currency` = the ORIGINAL entry currency
        # (ISO-4217); `currency_source` records which detection signal set it;
        # `amount_base` is the value in the canonical pivot (USD), derived at
        # write-time. Legacy rows are all USD (US-bank data), so base == amount.
        cols = [r[1] for r in c.execute("PRAGMA table_info(transactions)")]
        if "currency" not in cols:
            c.execute("ALTER TABLE transactions ADD COLUMN currency TEXT NOT NULL DEFAULT 'USD'")
        if "currency_source" not in cols:
            c.execute("ALTER TABLE transactions ADD COLUMN currency_source TEXT NOT NULL DEFAULT 'legacy'")
        if "amount_base" not in cols:
            c.execute("ALTER TABLE transactions ADD COLUMN amount_base REAL")
            # Backfill legacy rows: all USD, so base == amount. No rate lookups.
            c.execute("UPDATE transactions SET currency='USD', currency_source='legacy', "
                      "amount_base=amount WHERE amount_base IS NULL")

        # Currency on the net-worth / planning tables so the display toggle is
        # global. All existing data is USD.
        for tbl in ("accounts", "balance_snapshots", "budgets", "goals"):
            tcols = [r[1] for r in c.execute(f"PRAGMA table_info({tbl})")]
            if "currency" not in tcols:
                c.execute(f"ALTER TABLE {tbl} ADD COLUMN currency TEXT NOT NULL DEFAULT 'USD'")

        # FX rates: one direction only (base='USD'); invert in code for reverse.
        c.execute(
            """CREATE TABLE IF NOT EXISTS fx_rates (
                   rate_date  TEXT NOT NULL,
                   base       TEXT NOT NULL,
                   quote      TEXT NOT NULL,
                   rate       REAL NOT NULL,
                   source     TEXT NOT NULL DEFAULT 'frankfurter',
                   fetched_at TEXT,
                   PRIMARY KEY (rate_date, base, quote)
               )""")
        c.execute("CREATE INDEX IF NOT EXISTS idx_fx_lookup ON fx_rates(base, quote, rate_date)")


# ---- people ---------------------------------------------------------------

def list_people():
    with get_conn() as conn:
        return [dict(r) for r in conn.execute("SELECT * FROM people ORDER BY id")]


def rename_person(person_id, new_name):
    with get_conn() as conn:
        conn.execute("UPDATE people SET name=? WHERE id=?", (new_name, person_id))


# ---- transactions ---------------------------------------------------------

def add_transactions(person_id, rows, file_hash=None):
    """rows: list of dicts with keys date, description, amount, category, source,
    currency, currency_source, amount_base, and optional included (defaults to 1).
    file_hash links every row to the imported file (see imported_files)."""
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO transactions
               (person_id, date, description, amount, category, source,
                file_hash, included, balance, currency, currency_source, amount_base)
               VALUES (:person_id, :date, :description, :amount, :category,
                       :source, :file_hash, :included, :balance,
                       :currency, :currency_source, :amount_base)""",
            [{**r, "person_id": person_id, "file_hash": file_hash,
              "included": int(r.get("included", 1)),
              "balance": r.get("balance"),
              "currency": r.get("currency", "USD"),
              "currency_source": r.get("currency_source", "unknown"),
              "amount_base": r.get("amount_base")} for r in rows],
        )


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


def set_transaction_included(txn_id, included):
    """Toggle whether a single transaction counts toward calculations."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE transactions SET included=? WHERE id=?",
            (int(bool(included)), txn_id),
        )


def set_transaction_category(txn_id, category):
    """Recategorize a single transaction."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE transactions SET category=? WHERE id=?", (category, txn_id))


def get_transactions(person_id=None):
    q = "SELECT t.*, p.name AS person FROM transactions t JOIN people p ON p.id=t.person_id"
    params = ()
    if person_id is not None:
        q += " WHERE person_id=?"
        params = (person_id,)
    q += " ORDER BY date"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, params)]


def clear_transactions(person_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM transactions WHERE person_id=?", (person_id,))
        # Forget import history too, so files can be re-imported after a clear.
        conn.execute("DELETE FROM imported_files WHERE person_id=?", (person_id,))


# ---- import dedup ---------------------------------------------------------

def get_import(person_id, file_hash):
    """Return the import record for this file (dict) if already imported, else None."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM imported_files WHERE person_id=? AND file_hash=?",
            (person_id, file_hash),
        ).fetchone()
        return dict(row) if row else None


def record_import(person_id, file_hash, filename, count, imported_at):
    with get_conn() as conn:
        conn.execute(
            """INSERT OR IGNORE INTO imported_files
               (person_id, file_hash, filename, count, imported_at)
               VALUES (?, ?, ?, ?, ?)""",
            (person_id, file_hash, filename, count, imported_at),
        )


def list_imports(person_id=None):
    """Imported-file records with the person name and the live count of rows
    still in the DB for each. person_id=None returns every person's imports."""
    q = """SELECT f.*, p.name AS person,
                  (SELECT COUNT(*) FROM transactions t
                   WHERE t.person_id=f.person_id AND t.file_hash=f.file_hash)
                  AS live_count
           FROM imported_files f JOIN people p ON p.id=f.person_id"""
    params = ()
    if person_id is not None:
        q += " WHERE f.person_id=?"
        params = (person_id,)
    q += " ORDER BY f.imported_at DESC"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(q, params)]


def delete_import(person_id, file_hash):
    """Remove an imported file: its transactions and its import record."""
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM transactions WHERE person_id=? AND file_hash=?",
            (person_id, file_hash),
        )
        conn.execute(
            "DELETE FROM imported_files WHERE person_id=? AND file_hash=?",
            (person_id, file_hash),
        )
        return cur.rowcount


def count_untracked_transactions(person_id=None):
    """Rows imported before file-tracking existed (no file_hash). These can't be
    tied to a file in the UI and may contain whole-file duplicates.

    person_id=None (household/Joint) returns the count across ALL people.
    """
    with get_conn() as conn:
        if person_id is None:
            return conn.execute(
                "SELECT COUNT(*) FROM transactions WHERE file_hash IS NULL",
            ).fetchone()[0]
        return conn.execute(
            "SELECT COUNT(*) FROM transactions WHERE person_id=? AND file_hash IS NULL",
            (person_id,),
        ).fetchone()[0]


def clear_untracked_transactions(person_id):
    """Delete the untracked rows so the file(s) can be re-imported cleanly.
    Returns the number removed. (Exact-duplicate auto-merge is intentionally
    avoided: a statement can legitimately contain two identical rows, e.g. two
    equal wire-transfer fees on the same day.)"""
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM transactions WHERE person_id=? AND file_hash IS NULL",
            (person_id,),
        )
        return cur.rowcount


# ---- categories -----------------------------------------------------------

def get_categories(person_id):
    with get_conn() as conn:
        return [
            dict(r)
            for r in conn.execute(
                "SELECT * FROM categories WHERE person_id=? ORDER BY name", (person_id,)
            )
        ]


def upsert_category(person_id, name, keywords, parent=None):
    """Insert or update a category. `parent` is an optional rollup group name;
    pass None to leave an existing category's parent untouched."""
    with get_conn() as conn:
        if parent is None:
            conn.execute(
                """INSERT INTO categories(person_id, name, keywords) VALUES (?,?,?)
                   ON CONFLICT(person_id, name) DO UPDATE SET keywords=excluded.keywords""",
                (person_id, name, keywords),
            )
        else:
            conn.execute(
                """INSERT INTO categories(person_id, name, keywords, parent)
                   VALUES (?,?,?,?)
                   ON CONFLICT(person_id, name) DO UPDATE SET
                       keywords=excluded.keywords, parent=excluded.parent""",
                (person_id, name, keywords, parent),
            )


def delete_category(category_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM categories WHERE id=?", (category_id,))


# ---- vendor groups (drill-down rollups) -----------------------------------

def get_vendors(person_id):
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM vendors WHERE person_id=? ORDER BY name", (person_id,))]


def upsert_vendor(person_id, name, keywords):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO vendors(person_id, name, keywords) VALUES (?,?,?)
               ON CONFLICT(person_id, name) DO UPDATE SET keywords=excluded.keywords""",
            (person_id, name, keywords))


def delete_vendor(vendor_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM vendors WHERE id=?", (vendor_id,))


def category_parents(person_id):
    """Map of {category_name: parent_name} for a person (parent '' when unset)."""
    with get_conn() as conn:
        return {
            r["name"]: (r["parent"] or "")
            for r in conn.execute(
                "SELECT name, parent FROM categories WHERE person_id=?", (person_id,))
        }


# ---- budgets --------------------------------------------------------------

def get_budgets(person_id=None):
    """Budgets for a person, or household (person_id None) budgets."""
    with get_conn() as conn:
        if person_id is None:
            rows = conn.execute("SELECT * FROM budgets WHERE person_id IS NULL")
        else:
            rows = conn.execute("SELECT * FROM budgets WHERE person_id=?", (person_id,))
        return [dict(r) for r in rows]


def set_budget(person_id, category, amount, currency="USD"):
    """Upsert a monthly budget cap for a category (manual upsert so it also works
    for household budgets where person_id IS NULL — SQLite treats NULLs as
    distinct in UNIQUE constraints)."""
    with get_conn() as conn:
        if person_id is None:
            cur = conn.execute(
                "UPDATE budgets SET amount=?, currency=? WHERE person_id IS NULL AND category=?",
                (amount, currency, category))
        else:
            cur = conn.execute(
                "UPDATE budgets SET amount=?, currency=? WHERE person_id=? AND category=?",
                (amount, currency, person_id, category))
        if cur.rowcount == 0:
            conn.execute(
                "INSERT INTO budgets(person_id, category, amount, currency) VALUES (?,?,?,?)",
                (person_id, category, amount, currency))


def delete_budget(budget_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM budgets WHERE id=?", (budget_id,))


# ---- events & transaction tags --------------------------------------------

def create_event(person_id, name, kind, start_date=None, end_date=None, rule=None):
    """Create an event. `rule` may be a dict (stored as JSON) or a JSON string.
    Returns the new event id."""
    if isinstance(rule, (dict, list)):
        rule = json.dumps(rule)
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO events(person_id, name, kind, start_date, end_date, rule)
               VALUES (?,?,?,?,?,?)""",
            (person_id, name, kind, start_date, end_date, rule))
        return cur.lastrowid


def list_events(scope="all"):
    """Events for a scope: 'all' = everyone + household, None = household only,
    an int = that person's events plus household (person_id NULL)."""
    with get_conn() as conn:
        if scope == "all":
            rows = conn.execute("SELECT * FROM events ORDER BY name")
        elif scope is None:
            rows = conn.execute(
                "SELECT * FROM events WHERE person_id IS NULL ORDER BY name")
        else:
            rows = conn.execute(
                "SELECT * FROM events WHERE person_id=? OR person_id IS NULL "
                "ORDER BY name", (scope,))
        return [dict(r) for r in rows]


def delete_event(event_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM transaction_tags WHERE event_id=?", (event_id,))
        conn.execute("DELETE FROM events WHERE id=?", (event_id,))


def event_transaction_ids(event_id):
    """Transaction ids explicitly tagged to an event."""
    with get_conn() as conn:
        return [r["transaction_id"] for r in conn.execute(
            "SELECT transaction_id FROM transaction_tags WHERE event_id=?",
            (event_id,))]


def set_event_tags(event_id, transaction_ids):
    """Replace an event's explicit transaction membership with `transaction_ids`."""
    with get_conn() as conn:
        conn.execute("DELETE FROM transaction_tags WHERE event_id=?", (event_id,))
        conn.executemany(
            "INSERT OR IGNORE INTO transaction_tags(transaction_id, event_id) "
            "VALUES (?,?)", [(int(t), event_id) for t in transaction_ids])


# ---- goals ----------------------------------------------------------------

def get_goals(person_id="all"):
    """person_id: an int for one person, None for shared goals, 'all' for everything."""
    with get_conn() as conn:
        if person_id == "all":
            rows = conn.execute("SELECT * FROM goals ORDER BY horizon, target_date")
        elif person_id is None:
            rows = conn.execute("SELECT * FROM goals WHERE person_id IS NULL")
        else:
            rows = conn.execute("SELECT * FROM goals WHERE person_id=?", (person_id,))
        return [dict(r) for r in rows]


def add_goal(person_id, name, target_amount, saved_amount, target_date, horizon, notes,
             currency="USD"):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO goals
               (person_id, name, target_amount, saved_amount, target_date, horizon, notes, currency)
               VALUES (?,?,?,?,?,?,?,?)""",
            (person_id, name, target_amount, saved_amount, target_date, horizon, notes, currency),
        )


def update_goal_saved(goal_id, saved_amount):
    with get_conn() as conn:
        conn.execute("UPDATE goals SET saved_amount=? WHERE id=?", (saved_amount, goal_id))


def update_goal_notes(goal_id, notes):
    with get_conn() as conn:
        conn.execute("UPDATE goals SET notes=? WHERE id=?", (notes, goal_id))


def delete_goal(goal_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM goals WHERE id=?", (goal_id,))


# ---- accounts / net worth -------------------------------------------------

def add_account(person_id, name, kind, is_asset, balance, currency="USD"):
    """Create an account and write an initial snapshot dated today. Returns id."""
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO accounts(person_id, name, kind, is_asset, balance, updated_at, currency)
               VALUES (?,?,?,?,?,?,?)""",
            (person_id, name, kind, int(bool(is_asset)), float(balance), now, currency),
        )
        aid = cur.lastrowid
        conn.execute(
            """INSERT INTO balance_snapshots(account_id, date, balance, currency) VALUES (?,?,?,?)
               ON CONFLICT(account_id, date) DO UPDATE SET balance=excluded.balance""",
            (aid, date.today().isoformat(), float(balance), currency),
        )
        return aid


def get_account(account_id):
    """One account row (dict) or None — used to resolve an account's owner before
    populating its history from that person's imported statements."""
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM accounts WHERE id=?", (account_id,)).fetchone()
        return dict(row) if row else None


def list_accounts(person_id="all"):
    """person_id: int for one person, None for shared, 'all' for the household."""
    with get_conn() as conn:
        if person_id == "all":
            rows = conn.execute("SELECT * FROM accounts ORDER BY is_asset DESC, name")
        elif person_id is None:
            rows = conn.execute(
                "SELECT * FROM accounts WHERE person_id IS NULL ORDER BY name")
        else:
            rows = conn.execute(
                "SELECT * FROM accounts WHERE person_id=? ORDER BY name", (person_id,))
        return [dict(r) for r in rows]


def write_snapshot(account_id, snap_date, balance):
    """Upsert one snapshot (UNIQUE per account+day; same day overwrites)."""
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO balance_snapshots(account_id, date, balance) VALUES (?,?,?)
               ON CONFLICT(account_id, date) DO UPDATE SET balance=excluded.balance""",
            (account_id, snap_date, float(balance)),
        )


def update_account_balance(account_id, balance, snapshot_date=None):
    """Set the current balance and record a snapshot (today unless a date given,
    e.g. a statement's ending-balance date)."""
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute("UPDATE accounts SET balance=?, updated_at=? WHERE id=?",
                     (float(balance), now, account_id))
    write_snapshot(account_id, snapshot_date or date.today().isoformat(), balance)


def account_snapshots(account_id):
    """All snapshots for one account, oldest first — for its balance history chart."""
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT date, balance FROM balance_snapshots WHERE account_id=? "
            "ORDER BY date", (account_id,))]


def transactions_for_file(person_id, file_hash):
    """All transactions imported from one file, in file order (date, id) — used to
    derive month-end balances for a Net Worth account."""
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM transactions WHERE person_id=? AND file_hash=? "
            "ORDER BY date, id", (person_id, file_hash))]


def delete_account(account_id):
    """Delete an account and its snapshots (cascade in app logic)."""
    with get_conn() as conn:
        conn.execute("DELETE FROM balance_snapshots WHERE account_id=?", (account_id,))
        conn.execute("DELETE FROM accounts WHERE id=?", (account_id,))


def get_snapshots(person_id="all"):
    """Snapshots tagged with their account's is_asset (and person_id), scoped by
    view. Feeds analytics.net_worth_trend, which needs is_asset per snapshot."""
    q = ("SELECT s.account_id, s.date, s.balance, a.is_asset, a.person_id "
         "FROM balance_snapshots s JOIN accounts a ON a.id=s.account_id")
    with get_conn() as conn:
        if person_id == "all":
            rows = conn.execute(q + " ORDER BY s.date")
        elif person_id is None:
            rows = conn.execute(q + " WHERE a.person_id IS NULL ORDER BY s.date")
        else:
            rows = conn.execute(q + " WHERE a.person_id=? ORDER BY s.date", (person_id,))
        return [dict(r) for r in rows]


def get_uncategorized_descriptions(person_id):
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DISTINCT description FROM transactions "
            "WHERE person_id=? AND category='Uncategorized' AND description != ''",
            (person_id,),
        )
        return [r["description"] for r in rows]


def apply_category_mapping(person_id, mapping):
    """mapping: {description: category}. Updates all matching transactions."""
    with get_conn() as conn:
        for desc, cat in mapping.items():
            conn.execute(
                "UPDATE transactions SET category=? WHERE person_id=? AND description=?",
                (cat, person_id, desc),
            )
