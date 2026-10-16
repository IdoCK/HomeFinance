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
    assert d["alerts"] == []


def test_overview_series_trend(client, seeded):
    """The per-month trend powers the cash-flow area + savings-rate bars."""
    d = client.get("/api/overview", params={"person_id": seeded, "month": "2026-05"}).json()
    assert isinstance(d["series"], list) and len(d["series"]) == len(d["months"])
    may = next(p for p in d["series"] if p["month"] == "2026-05")
    assert may["income"] == 5000.0
    assert may["spend"] == 2400.0
    assert may["net"] == 2600.0
    assert "savings_rate" in may and "complete" in may


def test_overview_joint_split_per_person(client, people):
    """Joint view (no person_id) returns a per-person spend split for the
    dot-matrix; a single-persona view returns split=None."""
    from modules import database as db
    you, spouse = people[0]["id"], people[1]["id"]
    db.add_transactions(you, [
        {"date": "2026-05-01", "description": "Rent", "amount": -2000.0, "category": "Housing", "source": "bank"},
    ])
    db.add_transactions(spouse, [
        {"date": "2026-05-02", "description": "Groceries", "amount": -500.0, "category": "Groceries", "source": "card"},
    ])
    d = client.get("/api/overview", params={"month": "2026-05"}).json()
    assert d["split"] is not None
    by_id = {s["person_id"]: s["spend"] for s in d["split"]}
    assert by_id[you] == 2000.0
    assert by_id[spouse] == 500.0
    # Single-persona view → no split
    d2 = client.get("/api/overview", params={"person_id": you, "month": "2026-05"}).json()
    assert d2["split"] is None


def test_overview_includes_spending_alerts(client, people):
    from modules import database as db
    you = people[0]["id"]
    rows = []
    # Three complete baseline months of modest dining, then a spike in the latest.
    # Each month must span 1st..last day to count as "complete".
    for ym, last in (("2026-01", "31"), ("2026-02", "28"), ("2026-03", "31")):
        rows += [
            {"date": f"{ym}-01", "description": "Rent", "amount": -2000.0, "category": "Housing", "source": "bank"},
            {"date": f"{ym}-{last}", "description": "Dining", "amount": -100.0, "category": "Eating out", "source": "card"},
        ]
    rows += [
        {"date": "2026-04-01", "description": "Rent", "amount": -2000.0, "category": "Housing", "source": "bank"},
        {"date": "2026-04-30", "description": "Dining spree", "amount": -600.0, "category": "Eating out", "source": "card"},
    ]
    db.add_transactions(you, rows)
    d = client.get("/api/overview", params={"person_id": you}).json()
    cats = [a["category"] for a in d["alerts"]]
    assert "Eating out" in cats
