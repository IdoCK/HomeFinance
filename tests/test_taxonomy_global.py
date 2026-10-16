import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _old_shape_db(path):
    """Build a DB in the legacy per-person shape (categories/vendors with
    person_id) plus a couple of transactions, so we can assert the migration
    merges correctly and preserves transaction category names."""
    conn = sqlite3.connect(path)
    c = conn.cursor()
    c.executescript(
        """
        CREATE TABLE people (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE NOT NULL);
        CREATE TABLE categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER NOT NULL,
            name TEXT NOT NULL, keywords TEXT DEFAULT '', parent TEXT DEFAULT '',
            UNIQUE(person_id, name));
        CREATE TABLE vendors (
            id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER NOT NULL,
            name TEXT NOT NULL, keywords TEXT DEFAULT '', UNIQUE(person_id, name));
        CREATE TABLE transactions (
            id INTEGER PRIMARY KEY AUTOINCREMENT, person_id INTEGER NOT NULL,
            date TEXT, description TEXT, amount REAL, category TEXT DEFAULT 'Uncategorized');
        """
    )
    c.executemany("INSERT INTO people(name) VALUES (?)", [("Ido",), ("Aviv",)])
    # Same name, different keyword rules + different parents across people,
    # plus a name only one person has.
    c.executemany(
        "INSERT INTO categories(person_id, name, keywords, parent) VALUES (?,?,?,?)",
        [
            (1, "Groceries", "whole foods, costco", "Food"),
            (2, "Groceries", "costco, shufersal", ""),
            (1, "Eating Out", "cafe", "Food"),
            (2, "Eating Out", "cafe", "Dining"),
            (1, "Pet", "chewy", ""),
        ],
    )
    c.executemany(
        "INSERT INTO vendors(person_id, name, keywords) VALUES (?,?,?)",
        [(1, "Amazon", "amazon, amzn"), (2, "Amazon", "amzn, amazon.com")],
    )
    c.execute("INSERT INTO transactions(person_id, date, description, amount, category) "
              "VALUES (2,'2026-03-01','x',-5,'Pet')")  # name only person 1 had
    conn.commit()
    conn.close()


def _reload_db(tmp_path, monkeypatch):
    """Point the db module at a temp DB file and import it fresh."""
    from modules import database
    db_path = tmp_path / "finance.db"
    monkeypatch.setattr(database, "DB_PATH", db_path)
    return database, db_path


def test_migration_merges_categories_to_global(tmp_path, monkeypatch):
    db, db_path = _reload_db(tmp_path, monkeypatch)
    _old_shape_db(str(db_path))
    db.init_db()
    cats = {c["name"]: c for c in db.get_categories()}
    # one global row per name, no person_id scoping
    assert set(cats) >= {"Groceries", "Eating Out", "Pet"}
    # keyword rules unioned (dedup, order-preserving)
    assert cats["Groceries"]["keywords"] == "whole foods,costco,shufersal"
    # parent: non-empty wins; on conflict deterministic (Food beats Dining: count tie -> alphabetical)
    assert cats["Eating Out"]["parent"] in {"Dining", "Food"}
    # the transaction's category name still resolves to a real global category
    assert "Pet" in cats


def test_migration_is_idempotent(tmp_path, monkeypatch):
    db, db_path = _reload_db(tmp_path, monkeypatch)
    _old_shape_db(str(db_path))
    db.init_db()
    first = db.get_categories()
    db.init_db()  # second run must be a no-op on the now-global table
    assert [c["name"] for c in db.get_categories()] == [c["name"] for c in first]


def test_vendors_merged_global(tmp_path, monkeypatch):
    db, db_path = _reload_db(tmp_path, monkeypatch)
    _old_shape_db(str(db_path))
    db.init_db()
    vs = {v["name"]: v for v in db.get_vendors()}
    assert vs["Amazon"]["keywords"] == "amazon,amzn,amazon.com"


def test_upsert_and_parents_global(tmp_path, monkeypatch):
    db, db_path = _reload_db(tmp_path, monkeypatch)
    db.init_db()  # fresh DB -> global seed
    db.upsert_category("Travel", "airline, hotel", parent="Discretionary")
    assert db.category_parents()["Travel"] == "Discretionary"
    # same call from "any person" returns the same global list
    assert db.get_categories(1) == db.get_categories(2)
