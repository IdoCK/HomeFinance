"""Tests for event tagging: event_mask kinds (window / recurring / tagged + the
explicit-id union), filter_transactions(event=...), and the events DB CRUD."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

from modules import analytics
from modules import database as db


def _t(i, d, amount=-10, cat="Eating Out", person_id=1):
    return {"id": i, "date": d, "description": cat, "amount": amount,
            "category": cat, "source": "credit_card", "person_id": person_id,
            "included": 1}


TXNS = [
    _t(1, "2026-05-01"), _t(2, "2026-05-10"), _t(3, "2026-05-15"),
    _t(4, "2026-06-15"), _t(5, "2026-06-20"),
]


# ---- event_mask kinds via filter_transactions -----------------------------

def test_window_event():
    ev = {"kind": "window", "start_date": "2026-05-05", "end_date": "2026-05-20"}
    got = {t["id"] for t in analytics.filter_transactions(TXNS, event=ev)}
    assert got == {2, 3}


def test_recurring_month_day_event():
    # A birthday on the 15th of any month.
    ev = {"kind": "recurring", "rule": {"day_of_month": [15]}}
    got = {t["id"] for t in analytics.filter_transactions(TXNS, event=ev)}
    assert got == {3, 4}


def test_tagged_event_matches_only_ids():
    ev = {"kind": "tagged", "ids": [1, 5]}
    got = {t["id"] for t in analytics.filter_transactions(TXNS, event=ev)}
    assert got == {1, 5}


def test_window_unions_explicit_tags():
    # Window catches 2 & 3; an explicit tag pulls in 5 from outside the window.
    ev = {"kind": "window", "start_date": "2026-05-05", "end_date": "2026-05-20",
          "ids": [5]}
    got = {t["id"] for t in analytics.filter_transactions(TXNS, event=ev)}
    assert got == {2, 3, 5}


def test_rule_json_string_parsed():
    ev = {"kind": "recurring", "rule": '{"day_of_month": [1]}'}
    got = {t["id"] for t in analytics.filter_transactions(TXNS, event=ev)}
    assert got == {1}


# ---- DB CRUD --------------------------------------------------------------

@pytest.fixture
def fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", tmp_path / "test.db")
    db.init_db()
    return {p["name"]: p["id"] for p in db.list_people()}


def test_create_and_list_event_scoping(fresh_db):
    you, spouse = fresh_db["You"], fresh_db["Spouse"]
    db.create_event(you, "Trip", "window", "2026-05-01", "2026-05-07")
    db.create_event(None, "Paydays", "recurring", rule={"day_of_month": [1, 15]})
    db.create_event(spouse, "Sick days", "window", "2026-04-01", "2026-04-03")

    you_scope = {e["name"] for e in db.list_events(you)}
    assert you_scope == {"Trip", "Paydays"}          # own + household, not spouse's
    assert {e["name"] for e in db.list_events(None)} == {"Paydays"}
    assert {e["name"] for e in db.list_events("all")} == {"Trip", "Paydays", "Sick days"}


def test_rule_stored_as_json(fresh_db):
    eid = db.create_event(None, "Paydays", "recurring", rule={"day_of_month": [1, 15]})
    ev = [e for e in db.list_events("all") if e["id"] == eid][0]
    assert analytics._rule_of(ev) == {"day_of_month": [1, 15]}


def test_tag_set_and_read_and_delete(fresh_db):
    eid = db.create_event(None, "Wedding", "tagged")
    db.set_event_tags(eid, [3, 7, 9])
    assert set(db.event_transaction_ids(eid)) == {3, 7, 9}
    db.set_event_tags(eid, [3])                       # replace, not append
    assert db.event_transaction_ids(eid) == [3]
    db.delete_event(eid)
    assert eid not in {e["id"] for e in db.list_events("all")}
    assert db.event_transaction_ids(eid) == []        # tags cascade-deleted
