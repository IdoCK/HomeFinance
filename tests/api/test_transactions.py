import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def seeded(client, people):
    from modules import database as db
    you, spouse = people[0]["id"], people[1]["id"]
    db.add_transactions(you, [
        {"date": "2026-05-03", "description": "Whole Foods", "amount": -84.20,
         "category": "Groceries", "source": "card"},
        {"date": "2026-05-10", "description": "Paycheck", "amount": 4740.0,
         "category": "Income", "source": "bank"},
    ])
    db.add_transactions(spouse, [
        {"date": "2026-05-06", "description": "Chipotle", "amount": -31.55,
         "category": "Eating out", "source": "card"},
    ])
    return {"you": you, "spouse": spouse}


def test_all_transactions_when_no_person(client, seeded):
    r = client.get("/api/transactions")
    assert r.status_code == 200
    assert len(r.json()) == 3


def test_transactions_scoped_to_person(client, seeded):
    r = client.get("/api/transactions", params={"person_id": seeded["spouse"]})
    rows = r.json()
    assert len(rows) == 1
    assert rows[0]["description"] == "Chipotle"
    assert rows[0]["category"] == "Eating out"
