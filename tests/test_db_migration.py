"""Regression test for the legacy-name migration in init_db().

A DB that already carries the canonical 'Ido'/'Aviv' AND a stray legacy
'You'/'Spouse' row (re-seed cruft) used to crash init_db with a UNIQUE(name)
collision, because the migration renamed 'You' -> 'Ido' unconditionally.
"""
from modules import database as db


def test_init_db_collision_safe_with_stray_legacy_people(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "t.db")
    db.init_db()  # seeds Ido / Aviv

    # Simulate the broken state: canonical names present, plus stray legacy rows.
    with db.get_conn() as c:
        c.execute("INSERT INTO people(name) VALUES ('You')")
        c.execute("INSERT INTO people(name) VALUES ('Spouse')")

    # Re-running init_db must NOT raise (the rename is now guarded by NOT EXISTS).
    db.init_db()

    names = [p["name"] for p in db.list_people()]
    assert "Ido" in names and "Aviv" in names
    # The stray rows are left untouched (not renamed onto a taken name).
    assert names.count("Ido") == 1 and names.count("Aviv") == 1
