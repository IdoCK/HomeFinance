import pytest


@pytest.fixture()
def seeded(client, people):
    from modules import database as db
    you = people[0]["id"]
    # A fully-covered May (1st..31st present) so it counts as a complete month.
    db.add_transactions(you, [
        {"date": "2026-05-01", "description": "Rent", "amount": -2000.0,
         "category": "Housing", "source": "bank"},
        {"date": "2026-05-10", "description": "Paycheck", "amount": 5000.0,
         "category": "Income", "source": "bank"},
        {"date": "2026-05-15", "description": "Whole Foods", "amount": -300.0,
         "category": "Groceries", "source": "card"},
        {"date": "2026-05-31", "description": "Chipotle", "amount": -100.0,
         "category": "Eating out", "source": "card"},
    ])
    return you


def test_overview_headline_numbers(client, seeded):
    r = client.get("/api/overview", params={"person_id": seeded, "month": "2026-05"})
    assert r.status_code == 200
    d = r.json()
    assert d["month"] == "2026-05"
    assert d["income"] == 5000.0
    assert d["spend"] == 2400.0
    assert d["net"] == 2600.0
    assert d["by_category"]["Housing"] == 2000.0
    assert "2026-05" in d["months"]


def test_overview_empty_data(client, people):
    r = client.get("/api/overview", params={"person_id": people[0]["id"]})
    assert r.status_code == 200
    d = r.json()
    assert d["income"] == 0 and d["spend"] == 0 and d["net"] == 0
    assert d["months"] == [] and d["by_category"] == {}
    assert d["savings_rate"] is None
