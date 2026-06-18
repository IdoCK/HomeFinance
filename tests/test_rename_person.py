"""DB tests for renaming a household member (used by the sidebar rename UI)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from modules import database as db


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return {p["name"]: p["id"] for p in db.list_people()}


def test_rename_changes_name(fresh_db):
    you = fresh_db["You"]
    db.rename_person(you, "Alex")
    names = {p["id"]: p["name"] for p in db.list_people()}
    assert names[you] == "Alex"


def test_rename_keeps_data_linked_by_id(fresh_db):
    you = fresh_db["You"]
    db.add_transactions(you, [{"date": "2026-05-01", "description": "Rent",
                               "amount": -1500, "category": "Housing", "source": "bank"}])
    db.rename_person(you, "Sam")
    # Transactions are keyed by person_id, so they follow the rename.
    assert len(db.get_transactions(you)) == 1
