"""Tests for GET /import/untracked-count endpoint (Task 1.7).

Covers:
- Single person_id: returns count of file_hash IS NULL rows for that person only.
- Household (person_id omitted): returns count across ALL people.
- person_id with zero untracked rows returns 0.
"""
import pytest


TRACKED_ROW = {
    "date": "2026-01-01", "description": "TRACKED", "amount": -10.0,
    "category": "Food", "source": "bank", "included": True, "balance": None,
}
UNTRACKED_ROW = {
    "date": "2026-01-02", "description": "UNTRACKED", "amount": -20.0,
    "category": "Food", "source": "bank", "included": True, "balance": None,
}


def _commit_tracked(client, person_id, file_hash="aabbcc" + "0" * 58):
    """Commit a row with a real file_hash (tracked)."""
    r = client.post("/api/import/commit", json={
        "person_id": person_id,
        "filename": "tracked.csv",
        "file_hash": file_hash,
        "source": "bank",
        "rows": [TRACKED_ROW],
    })
    assert r.status_code == 200


def _insert_untracked(client, person_id):
    """Directly insert a row without a file_hash (legacy/untracked).
    We do this via the DB directly using the monkeypatched db module."""
    from modules import database as db
    with db.get_conn() as conn:
        conn.execute(
            "INSERT INTO transactions (person_id, date, description, amount, "
            "category, source, included, file_hash) VALUES (?,?,?,?,?,?,?,NULL)",
            (person_id, "2026-01-03", "LEGACY", -5.0, "Food", "bank", 1),
        )


class TestUntrackedCount:

    def test_single_person_no_untracked(self, client, people):
        """With only tracked rows, count must be 0."""
        pid = people[0]["id"]
        _commit_tracked(client, pid)
        r = client.get("/api/import/untracked-count", params={"person_id": pid})
        assert r.status_code == 200
        assert r.json() == {"count": 0}

    def test_single_person_with_untracked(self, client, people):
        """One tracked + one untracked: count = 1."""
        pid = people[0]["id"]
        _commit_tracked(client, pid)
        _insert_untracked(client, pid)
        r = client.get("/api/import/untracked-count", params={"person_id": pid})
        assert r.status_code == 200
        assert r.json()["count"] == 1

    def test_single_person_only_their_rows(self, client, people):
        """Untracked rows for person B must NOT appear in person A's count."""
        pid_a = people[0]["id"]
        pid_b = people[1]["id"]
        _insert_untracked(client, pid_b)  # insert for B
        r = client.get("/api/import/untracked-count", params={"person_id": pid_a})
        assert r.status_code == 200
        assert r.json()["count"] == 0

    def test_household_sums_across_people(self, client, people):
        """person_id omitted → count across all people."""
        pid_a = people[0]["id"]
        pid_b = people[1]["id"]
        _insert_untracked(client, pid_a)
        _insert_untracked(client, pid_b)
        _commit_tracked(client, pid_a)  # tracked row should NOT be counted
        r = client.get("/api/import/untracked-count")
        assert r.status_code == 200
        assert r.json()["count"] == 2

    def test_household_zero_when_all_tracked(self, client, people):
        """No untracked rows at all → household count is 0."""
        for p in people:
            _commit_tracked(client, p["id"], file_hash="aa" + str(p["id"]).zfill(62))
        r = client.get("/api/import/untracked-count")
        assert r.status_code == 200
        assert r.json()["count"] == 0
