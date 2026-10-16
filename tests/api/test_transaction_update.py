import pytest


@pytest.fixture()
def one_txn(client, people):
    from modules import database as db
    pid = people[0]["id"]
    db.add_transactions(pid, [
        {"date": "2026-05-03", "description": "Chewy", "amount": -52.0,
         "category": "Uncategorized", "source": "card"},
    ])
    return db.get_transactions(pid)[0]


def test_update_category(client, one_txn):
    r = client.patch(f"/api/transactions/{one_txn['id']}", json={"category": "Dog"})
    assert r.status_code == 200
    assert r.json()["category"] == "Dog"


def test_toggle_included(client, one_txn):
    r = client.patch(f"/api/transactions/{one_txn['id']}", json={"included": False})
    assert r.status_code == 200
    assert r.json()["included"] == 0


def test_update_missing_txn_404(client):
    r = client.patch("/api/transactions/999999", json={"category": "X"})
    assert r.status_code == 404
