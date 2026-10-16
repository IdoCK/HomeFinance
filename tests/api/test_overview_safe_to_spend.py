import pytest


@pytest.fixture()
def seeded_safe(client, people):
    """A monthly Netflix subscription (detected as committed) + May income and a
    one-off discretionary grocery run, so the committed/discretionary split and
    safe-to-spend are determinate."""
    from modules import database as db
    you = people[0]["id"]
    txns = []
    for m in range(1, 6):  # Jan..May, monthly cadence -> recurring
        txns.append({"date": f"2026-0{m}-15", "description": "Netflix",
                     "amount": -15.0, "category": "Subscriptions", "source": "card"})
    txns.append({"date": "2026-05-10", "description": "Paycheck", "amount": 5000.0,
                 "category": "Income", "source": "bank"})
    txns.append({"date": "2026-05-20", "description": "Whole Foods", "amount": -300.0,
                 "category": "Groceries", "source": "card"})
    db.add_transactions(you, txns)
    return you


def test_safe_to_spend_reserves_committed_and_subtracts_discretionary(client, seeded_safe):
    d = client.get("/api/overview", params={"person_id": seeded_safe, "month": "2026-05"}).json()
    # committed = expected monthly recurring obligations (Netflix $15)
    assert d["committed"] == pytest.approx(15.0, abs=0.5)
    # this month's spend split: $15 committed (Netflix) + $300 discretionary (groceries)
    assert d["committed_spent"] == pytest.approx(15.0, abs=0.5)
    assert d["discretionary_spent"] == pytest.approx(300.0, abs=0.5)
    # safe = income - committed - discretionary_spent = 5000 - 15 - 300
    assert d["safe_to_spend"] == pytest.approx(4685.0, abs=1.0)


def test_safe_to_spend_fields_present_when_empty(client, people):
    d = client.get("/api/overview", params={"person_id": people[0]["id"]}).json()
    assert d["safe_to_spend"] == 0.0
    assert d["committed"] == 0.0
    assert d["committed_spent"] == 0.0
    assert d["discretionary_spent"] == 0.0
