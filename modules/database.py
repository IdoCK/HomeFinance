"""SQLite storage for the household finance dashboard.

All data lives in a single local file (data/finance.db). Nothing leaves the
machine except the anonymized summaries sent for AI insights (see ai_insights.py).
"""

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
            """
        )
        # Seed the two members once.
        for name in ("You", "Spouse"):
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
    and optional included (defaults to 1). file_hash links every row to the
    imported file (see imported_files)."""
    with get_conn() as conn:
        conn.executemany(
            """INSERT INTO transactions
               (person_id, date, description, amount, category, source,
                file_hash, included)
               VALUES (:person_id, :date, :description, :amount, :category,
                       :source, :file_hash, :included)""",
            [{**r, "person_id": person_id, "file_hash": file_hash,
              "included": int(r.get("included", 1))} for r in rows],
        )


def set_transaction_included(txn_id, included):
    """Toggle whether a single transaction counts toward calculations."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE transactions SET included=? WHERE id=?",
            (int(bool(included)), txn_id),
        )


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


def count_untracked_transactions(person_id):
    """Rows imported before file-tracking existed (no file_hash). These can't be
    tied to a file in the UI and may contain whole-file duplicates."""
    with get_conn() as conn:
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


def upsert_category(person_id, name, keywords):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO categories(person_id, name, keywords) VALUES (?,?,?)
               ON CONFLICT(person_id, name) DO UPDATE SET keywords=excluded.keywords""",
            (person_id, name, keywords),
        )


def delete_category(category_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM categories WHERE id=?", (category_id,))


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


def add_goal(person_id, name, target_amount, saved_amount, target_date, horizon, notes):
    with get_conn() as conn:
        conn.execute(
            """INSERT INTO goals
               (person_id, name, target_amount, saved_amount, target_date, horizon, notes)
               VALUES (?,?,?,?,?,?,?)""",
            (person_id, name, target_amount, saved_amount, target_date, horizon, notes),
        )


def update_goal_saved(goal_id, saved_amount):
    with get_conn() as conn:
        conn.execute("UPDATE goals SET saved_amount=? WHERE id=?", (saved_amount, goal_id))


def delete_goal(goal_id):
    with get_conn() as conn:
        conn.execute("DELETE FROM goals WHERE id=?", (goal_id,))


# ---- accounts / net worth -------------------------------------------------

def add_account(person_id, name, kind, is_asset, balance):
    """Create an account and write an initial snapshot dated today. Returns id."""
    now = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        cur = conn.execute(
            """INSERT INTO accounts(person_id, name, kind, is_asset, balance, updated_at)
               VALUES (?,?,?,?,?,?)""",
            (person_id, name, kind, int(bool(is_asset)), float(balance), now),
        )
        aid = cur.lastrowid
        conn.execute(
            """INSERT INTO balance_snapshots(account_id, date, balance) VALUES (?,?,?)
               ON CONFLICT(account_id, date) DO UPDATE SET balance=excluded.balance""",
            (aid, date.today().isoformat(), float(balance)),
        )
        return aid


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
