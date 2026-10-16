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


@pytest.fixture()
def seeded_joint(client, people):
    """Both people spend, with one shared category (Groceries) and one each unique."""
    from modules import database as db
    a, b = people[0]["id"], people[1]["id"]
    db.add_transactions(a, [
        {"date": "2026-05-05", "description": "Rent", "amount": -2000.0, "category": "Housing", "source": "bank"},
        {"date": "2026-05-12", "description": "Whole Foods", "amount": -300.0, "category": "Groceries", "source": "card"},
    ])
    db.add_transactions(b, [
        {"date": "2026-05-09", "description": "Trader Joes", "amount": -100.0, "category": "Groceries", "source": "card"},
        {"date": "2026-05-20", "description": "Dinner out", "amount": -50.0, "category": "Dining", "source": "card"},
    ])
    return {"a": people[0], "b": people[1]}


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
    db.upsert_category("Housing", "", "Essentials")
    db.upsert_category("Groceries", "", "Essentials")
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


def test_drill_category_ranks_spend(client, seeded):
    d = client.get("/api/analysis/drill", params={"person_id": seeded, "level": "category"}).json()
    assert d["level"] == "category"
    by = {i["name"]: i["value"] for i in d["items"]}
    assert by["Housing"] == 4000.0
    assert by["Groceries"] == 550.0
    assert d["items"][0]["name"] == "Housing"  # biggest first
    assert d["rows"] == []


def test_drill_vendor_within_category(client, seeded):
    d = client.get("/api/analysis/drill",
                   params={"person_id": seeded, "level": "vendor", "cat": "Groceries"}).json()
    assert d["level"] == "vendor"
    names = {i["name"] for i in d["items"]}
    # Whole Foods is the only Groceries vendor; vendor_of derives it from the desc.
    assert any("whole" in n.lower() or "foods" in n.lower() for n in names)
    assert sum(i["value"] for i in d["items"]) == 550.0


def test_drill_rows_leaf(client, seeded):
    vend = client.get("/api/analysis/drill",
                      params={"person_id": seeded, "level": "vendor", "cat": "Groceries"}).json()
    vendor = vend["items"][0]["name"]
    d = client.get("/api/analysis/drill",
                   params={"person_id": seeded, "level": "rows", "cat": "Groceries", "vendor": vendor}).json()
    assert d["level"] == "rows"
    assert len(d["rows"]) == 2
    assert {r["amount"] for r in d["rows"]} == {-300.0, -250.0}
    # newest first
    assert d["rows"][0]["date"] >= d["rows"][1]["date"]


def test_compare_month_vs_month(client, seeded):
    # Seeded spans 2026-04 and 2026-05. Bucket A = most recent month, B = previous.
    d = client.get("/api/analysis/compare",
                   params={"person_id": seeded, "preset": "month_vs_month", "metric": "spend"}).json()
    assert d["preset"] == "month_vs_month"
    assert [b["label"] for b in d["buckets"]] == ["2026-05", "2026-04"]
    totals = {b["label"]: b["total"] for b in d["buckets"]}
    assert totals["2026-05"] == 2250.0   # Housing 2000 + Groceries 250
    assert totals["2026-04"] == 2300.0   # Housing 2000 + Groceries 300
    cats = {c["name"]: c for c in d["categories"]}
    assert cats["Housing"]["a"] == 2000.0 and cats["Housing"]["b"] == 2000.0
    assert cats["Groceries"]["a"] == 250.0 and cats["Groceries"]["b"] == 300.0
    assert d["categories"][0]["name"] == "Housing"  # biggest combined first


def test_compare_weekdays_weekends(client, seeded):
    # Apr 5 (Sun) + Apr 12 (Sun) are weekends; May 5 (Tue) + May 18 (Mon) weekdays.
    d = client.get("/api/analysis/compare",
                   params={"person_id": seeded, "preset": "weekdays_weekends", "metric": "spend"}).json()
    assert d["labels"] == {"a": "Weekdays", "b": "Weekends"}
    totals = {b["label"]: b["total"] for b in d["buckets"]}
    assert totals["Weekdays"] == 2250.0   # May rows
    assert totals["Weekends"] == 2300.0   # April rows
    cats = {c["name"]: c for c in d["categories"]}
    assert cats["Groceries"]["a"] == 250.0  # weekday Groceries (May 18)
    assert cats["Groceries"]["b"] == 300.0  # weekend Groceries (Apr 12)


def test_compare_per_day_metric(client, seeded):
    d = client.get("/api/analysis/compare",
                   params={"person_id": seeded, "preset": "weekdays_weekends", "metric": "per_day"}).json()
    assert d["metric"] == "per_day"
    for b in d["buckets"]:
        assert b["n_days"] > 0
        assert b["per_day"] == pytest.approx(b["total"] / b["n_days"], abs=0.01)


def test_compare_empty(client, people):
    d = client.get("/api/analysis/compare", params={"person_id": people[0]["id"]}).json()
    assert d["categories"] == []
    assert all(b["total"] == 0 for b in d["buckets"])


def test_overlap_per_category_split(client, seeded_joint):
    d = client.get("/api/analysis/overlap").json()
    assert d["available"] is True
    assert d["a"]["name"] == seeded_joint["a"]["name"]
    assert d["a"]["spend"] == 2300.0   # Housing 2000 + Groceries 300
    assert d["b"]["spend"] == 150.0    # Groceries 100 + Dining 50
    rows = {r["category"]: r for r in d["rows"]}
    # Groceries is the only mutual category
    assert rows["Groceries"]["shared"] is True
    assert rows["Groceries"]["a"] == 300.0 and rows["Groceries"]["b"] == 100.0
    assert rows["Housing"]["shared"] is False
    assert rows["Dining"]["shared"] is False
    assert d["shared"] == 1
    # ranked by combined spend (Housing 2000 biggest)
    assert d["rows"][0]["category"] == "Housing"


def test_dow_filter_selects_specific_weekdays(client, seeded):
    # Apr 5 & Apr 12 are Sundays (dow=6); May rows are weekdays. Sunday-only → April.
    d = client.get("/api/analysis/category-trend",
                   params={"person_id": seeded, "dow": [6]}).json()
    assert d["months"] == ["2026-04"]


def test_filters_and_together_dow_and_category(client, seeded):
    # dow=6 (Sundays) AND categories=Groceries → just the Apr 12 grocery run.
    d = client.get("/api/analysis/drill",
                   params={"person_id": seeded, "level": "category",
                           "dow": [6], "categories": ["Groceries"]}).json()
    by = {i["name"]: i["value"] for i in d["items"]}
    assert by == {"Groceries": 300.0}  # Housing excluded by category, May excluded by dow


def test_window_event_auto_includes_in_range(client, seeded):
    # A date-window event (no manual tags) should scope the analysis to April only.
    from modules import database as db
    eid = db.create_event(seeded, "April", "window", "2026-04-01", "2026-04-30", None)
    d = client.get("/api/analysis/drill",
                   params={"person_id": seeded, "level": "category", "event_id": eid}).json()
    by = {i["name"]: i["value"] for i in d["items"]}
    assert by == {"Housing": 2000.0, "Groceries": 300.0}  # Apr 5 + Apr 12, no May rows


def test_recurring_event_auto_includes_by_dow(client, seeded):
    # A recurring Sundays rule selects the two April Sunday rows.
    from modules import database as db
    eid = db.create_event(seeded, "Sundays", "recurring", None, None, {"dow": [6]})
    d = client.get("/api/analysis/drill",
                   params={"person_id": seeded, "level": "category", "event_id": eid}).json()
    by = {i["name"]: i["value"] for i in d["items"]}
    assert by == {"Housing": 2000.0, "Groceries": 300.0}


def test_overlap_respects_category_filter(client, seeded_joint):
    d = client.get("/api/analysis/overlap", params={"categories": ["Groceries"]}).json()
    cats = [r["category"] for r in d["rows"]]
    assert cats == ["Groceries"]
    assert d["a"]["spend"] == 300.0 and d["b"]["spend"] == 100.0
