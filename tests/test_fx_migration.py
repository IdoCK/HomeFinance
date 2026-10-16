import sqlite3
from modules import database


def _seed_legacy_row(db_path):
    """Insert a transaction the OLD way (no currency columns) to simulate a
    pre-migration DB, then run init_db to migrate it."""
    conn = sqlite3.connect(db_path)
    conn.executescript(
        """CREATE TABLE IF NOT EXISTS people(id INTEGER PRIMARY KEY, name TEXT);
           CREATE TABLE IF NOT EXISTS transactions(
             id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER, date TEXT,
             description TEXT, amount REAL, category TEXT, source TEXT,
             included INTEGER DEFAULT 1, balance REAL);"""
    )
    conn.execute("INSERT INTO people(id,name) VALUES (1,'Ido')")
    conn.execute(
        "INSERT INTO transactions(person_id,date,description,amount) "
        "VALUES (1,'2026-03-13','ILLUMINA PAYROLL',3684.08)")
    conn.commit()
    conn.close()


def test_migration_adds_columns_and_backfills_usd(tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    _seed_legacy_row(db_path)

    database.init_db()

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cols = {r[1] for r in conn.execute("PRAGMA table_info(transactions)")}
    assert {"currency", "currency_source", "amount_base"} <= cols

    row = conn.execute("SELECT * FROM transactions WHERE description='ILLUMINA PAYROLL'").fetchone()
    assert row["currency"] == "USD"
    assert row["currency_source"] == "legacy"
    assert row["amount_base"] == 3684.08  # USD pivot: base == amount

    fx_cols = {r[1] for r in conn.execute("PRAGMA table_info(fx_rates)")}
    assert {"rate_date", "base", "quote", "rate", "source", "fetched_at"} <= fx_cols
    conn.close()
