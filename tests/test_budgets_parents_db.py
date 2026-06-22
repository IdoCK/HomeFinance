"""DB-roundtrip tests for the budget + parent-category persistence the new
Categories-tab UI relies on. Each test runs against a throwaway SQLite file so it
never touches the real data/finance.db."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from modules import database as db


@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    people = {p["name"]: p["id"] for p in db.list_people()}
    return people


def test_set_and_get_budget_roundtrip(fresh_db):
    pid = fresh_db["Ido"]
    db.set_budget(pid, "Groceries", 400)
    got = {b["category"]: b["amount"] for b in db.get_budgets(pid)}
    assert got["Groceries"] == 400


def test_set_budget_is_upsert(fresh_db):
    pid = fresh_db["Ido"]
    db.set_budget(pid, "Transit", 50)
    db.set_budget(pid, "Transit", 75)            # update, not duplicate
    rows = [b for b in db.get_budgets(pid) if b["category"] == "Transit"]
    assert len(rows) == 1 and rows[0]["amount"] == 75


def test_household_budget_is_separate_from_person(fresh_db):
    pid = fresh_db["Ido"]
    db.set_budget(pid, "Food", 300)
    db.set_budget(None, "Food", 900)             # person_id NULL = household
    assert {b["amount"] for b in db.get_budgets(pid)} == {300}
    assert {b["amount"] for b in db.get_budgets(None)} == {900}


def test_parent_assignment_roundtrip(fresh_db):
    pid = fresh_db["Ido"]
    db.upsert_category(pid, "Groceries", "whole foods", parent="Food")
    db.upsert_category(pid, "Eating Out", "restaurant", parent="Food")
    parents = db.category_parents(pid)
    assert parents["Groceries"] == "Food"
    assert parents["Eating Out"] == "Food"


def test_clearing_parent_unsets_it(fresh_db):
    pid = fresh_db["Ido"]
    db.upsert_category(pid, "Groceries", "whole foods", parent="Food")
    db.upsert_category(pid, "Groceries", "whole foods", parent="")   # clear
    assert db.category_parents(pid)["Groceries"] == ""


def test_view_budget_union_sums_per_category(fresh_db):
    # Mirrors app._view_budgets Household aggregation: sum per category across people.
    you, spouse = fresh_db["Ido"], fresh_db["Aviv"]
    db.set_budget(you, "Food", 300)
    db.set_budget(spouse, "Food", 200)
    db.set_budget(spouse, "Transit", 40)
    totals = {}
    for p in (you, spouse):
        for b in db.get_budgets(p):
            totals[b["category"]] = totals.get(b["category"], 0.0) + float(b["amount"])
    assert totals["Food"] == 500
    assert totals["Transit"] == 40
