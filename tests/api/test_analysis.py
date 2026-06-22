import pytest


@pytest.fixture()
def seeded(client, people):
    """Two months of spend across a couple categories, single persona."""
    from modules import database as db
    you = people[0]["id"]
    db.add_transactions(you, [
        {"date": "2026-04-05", "description": "Rent", "amount": -2000.0, "category": "Housing", "source": "bank"},
        {"date": "2026-04-12", "description": "Whole Foods", "amount": -300.0, "category": "Groceries", "source": "card"},
        {"date": "2026-05-05", "description": "Rent", "amount": -2000.0, "category": "Housing", "source": "bank"},
        {"date": "2026-05-18", "description": "Whole Foods", "amount": -250.0, "category": "Groceries", "source": "card"},
    ])
    return you


def test_filter_options_lists_months_and_categories(client, seeded):
    d = client.get("/api/analysis/filter-options", params={"person_id": seeded}).json()
    assert d["months"] == ["2026-04", "2026-05"]
    assert set(d["categories"]) == {"Housing", "Groceries"}
    assert d["events"] == []


def test_category_trend_series_align_to_months(client, seeded):
    d = client.get("/api/analysis/category-trend", params={"person_id": seeded}).json()
    assert d["months"] == ["2026-04", "2026-05"]
    by_name = {s["name"]: s for s in d["series"]}
    # Biggest spender first
    assert d["series"][0]["name"] == "Housing"
    assert by_name["Housing"]["values"] == [2000.0, 2000.0]
    assert by_name["Groceries"]["values"] == [300.0, 250.0]
    assert by_name["Housing"]["total"] == 4000.0


def test_category_trend_rollup_groups_under_parent(client, seeded):
    from modules import database as db
    # Roll Housing + Groceries up under a "Essentials" parent.
    db.upsert_category(seeded, "Housing", "", "Essentials")
    db.upsert_category(seeded, "Groceries", "", "Essentials")
    d = client.get("/api/analysis/category-trend",
                   params={"person_id": seeded, "rollup": "true"}).json()
    names = [s["name"] for s in d["series"]]
    assert names == ["Essentials"]
    assert d["series"][0]["values"] == [2300.0, 2250.0]


def test_category_trend_month_filter(client, seeded):
    d = client.get("/api/analysis/category-trend",
                   params={"person_id": seeded, "months": ["2026-05"]}).json()
    assert d["months"] == ["2026-05"]
    by_name = {s["name"]: s for s in d["series"]}
    assert by_name["Housing"]["values"] == [2000.0]


def test_category_trend_empty(client, people):
    d = client.get("/api/analysis/category-trend", params={"person_id": people[0]["id"]}).json()
    assert d == {"months": [], "series": []}
