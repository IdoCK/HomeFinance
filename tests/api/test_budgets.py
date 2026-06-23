from datetime import date


def test_budgets_status_for_current_month(client, people):
    from modules import database as db
    you = people[0]["id"]
    today = date.today().isoformat()
    db.add_transactions(you, [
        {"date": today, "description": "Whole Foods", "amount": -120.0,
         "category": "Groceries", "source": "card"},
    ])
    db.set_budget(you, "Groceries", 400.0)

    r = client.get("/api/budgets", params={"person_id": you})
    assert r.status_code == 200
    g = next(b for b in r.json() if b["category"] == "Groceries")
    assert g["budget"] == 400.0
    assert g["spent"] == 120.0
    assert g["status"] in ("on_track", "ahead", "over")


def test_budget_summary_rollup_and_unbudgeted(client, people):
    from modules import database as db
    you = people[0]["id"]
    today = date.today().isoformat()
    db.add_transactions(you, [
        {"date": today, "description": "Whole Foods", "amount": -120.0, "category": "Groceries", "source": "card"},
        {"date": today, "description": "Chipotle", "amount": -50.0, "category": "Eating out", "source": "card"},
    ])
    db.set_budget(you, "Groceries", 400.0)

    s = client.get("/api/budgets/summary", params={"person_id": you}).json()
    assert s["total_budgeted"] == 400.0
    assert s["total_spent"] == 120.0          # spend on budgeted categories
    assert s["unbudgeted_spent"] == 50.0      # Eating out has no budget


def test_put_budget_upserts(client, people):
    you = people[0]["id"]
    r = client.put("/api/budgets", json={"person_id": you, "category": "Rent", "amount": 2000.0})
    assert r.status_code == 200
    rows = client.get("/api/budgets", params={"person_id": you}).json()
    assert any(b["category"] == "Rent" and b["budget"] == 2000.0 for b in rows)


def test_delete_budget(client, people):
    you = people[0]["id"]
    client.put("/api/budgets", json={"person_id": you, "category": "Rent", "amount": 2000.0})
    bid = next(b["id"] for b in client.get("/api/budgets", params={"person_id": you}).json()
               if b["category"] == "Rent")
    assert client.delete(f"/api/budgets/{bid}").status_code == 200
    rows = client.get("/api/budgets", params={"person_id": you}).json()
    assert not any(b["category"] == "Rent" for b in rows)
