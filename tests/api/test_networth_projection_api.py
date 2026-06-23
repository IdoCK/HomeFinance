def test_projection_endpoint_projects_from_current_net(client, people):
    from modules import database as db
    you = people[0]["id"]
    # A complete May with $5000 in, $3000 out -> $2000/mo average savings.
    db.add_transactions(you, [
        {"date": "2026-05-01", "description": "Rent", "amount": -3000.0, "category": "Housing", "source": "bank"},
        {"date": "2026-05-31", "description": "Paycheck", "amount": 5000.0, "category": "Income", "source": "bank"},
    ])
    db.add_account(you, "Brokerage", "investment", 1, 10000.0, "USD")

    d = client.get("/api/networth/projection", params={"person_id": you, "annual_return": 0.07, "years": 10}).json()
    assert d["annual_return"] == 0.07
    assert d["monthly_savings"] == 2000.0
    assert d["current_net"] == 10000.0
    assert len(d["points"]) == 120
    last = d["points"][-1]
    # Compounding outgrows the straight-line contribution sum.
    assert last["compounding"] > last["linear"]
    assert last["linear"] == 10000 + 2000 * 120


def test_projection_endpoint_defaults(client, people):
    d = client.get("/api/networth/projection", params={"person_id": people[0]["id"]}).json()
    assert d["annual_return"] == 0.07            # default rate
    assert d["current_net"] == 0.0
    assert d["points"] == []                      # no savings, no accounts -> nothing to project
