"""Analysis & Insights must run on the USD base (amount_base), like every other
money router, and scale to the display currency last. Regression guard for the
CRITICAL finding: Analysis summed raw original-currency amounts, so the same
category diverged between Overview and Analysis the moment a non-USD row existed.
"""
from datetime import date


def _seed_mixed(client, monkeypatch):
    """One ILS spend (-2000 ILS == -500 USD at USD->ILS 4.0) + one USD spend."""
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": 4.0}})
    pid = client.get("/api/people").json()[0]["id"]
    client.post("/api/import/commit", json={
        "person_id": pid, "filename": "f.csv", "file_hash": "h", "source": "bank",
        "rows": [
            {"date": "2026-05-05", "description": "SUPER", "amount": -2000.0,
             "currency": "ILS", "category": "Groceries"},
            {"date": "2026-05-06", "description": "SHOP", "amount": -100.0,
             "currency": "USD", "category": "Shopping"},
        ]})
    return pid


def test_category_trend_sums_usd_base_not_raw(client, monkeypatch):
    pid = _seed_mixed(client, monkeypatch)
    d = client.get("/api/analysis/category-trend", params={"person_id": pid}).json()
    by = {s["name"]: s for s in d["series"]}
    # ILS -2000 at USD->ILS 4.0 is -500 USD base. Must be 500 (base), not 2000 (raw).
    assert by["Groceries"]["total"] == 500.0
    assert by["Shopping"]["total"] == 100.0


def test_category_trend_matches_overview_total(client, monkeypatch):
    """The same category must read identically on Overview and Analysis."""
    pid = _seed_mixed(client, monkeypatch)
    ov = client.get("/api/overview", params={"person_id": pid, "month": "2026-05"}).json()
    tr = client.get("/api/analysis/category-trend", params={"person_id": pid}).json()
    tr_by = {s["name"]: s["total"] for s in tr["series"]}
    assert tr_by["Groceries"] == ov["by_category"]["Groceries"] == 500.0


def test_drill_sums_usd_base(client, monkeypatch):
    pid = _seed_mixed(client, monkeypatch)
    d = client.get("/api/analysis/drill",
                   params={"person_id": pid, "level": "category"}).json()
    by = {i["name"]: i["value"] for i in d["items"]}
    assert by["Groceries"] == 500.0
    assert by["Shopping"] == 100.0


def test_compare_sums_usd_base(client, monkeypatch):
    pid = _seed_mixed(client, monkeypatch)
    d = client.get("/api/analysis/compare",
                   params={"person_id": pid, "preset": "weekdays_weekends",
                           "metric": "spend"}).json()
    total = sum(b["total"] for b in d["buckets"])
    assert total == 600.0  # 500 (ILS base) + 100 (USD), never 2100 (raw)


def test_category_trend_scales_to_display(client, monkeypatch):
    from modules import fx
    pid = _seed_mixed(client, monkeypatch)
    fx.upsert_rate(date.today().isoformat(), "USD", "ILS", 3.0)
    d = client.get("/api/analysis/category-trend",
                   params={"person_id": pid, "display": "ILS"}).json()
    by = {s["name"]: s for s in d["series"]}
    assert by["Groceries"]["total"] == 1500.0   # 500 USD base * 3
    assert by["Shopping"]["total"] == 300.0      # 100 USD base * 3
