"""
Task 1.6 – uncategorized count/amount on the Overview endpoint.

RED/GREEN guard: verifies that the overview response contains
  uncategorized: { count: int, amount: float }
where:
  - count = number of expense rows (amount < 0) with category in
    ("Uncategorized", "", None) for the selected month
  - amount = category_totals-based USD base spend, scaled to display,
    so it is consistent with by_category["Uncategorized"]

Mixed-currency case proves that `amount` uses the USD base value,
not the raw original-currency amount.
"""
from datetime import date


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _seed_uncategorized(client, monkeypatch):
    """Seed one USD uncategorized expense and one USD categorized expense."""
    pid = client.get("/api/people").json()[0]["id"]
    client.post("/api/import/commit", json={
        "person_id": pid, "filename": "f.csv", "file_hash": "h1", "source": "bank",
        "rows": [
            {"date": "2026-05-10", "description": "UNKNOWN_A",
             "amount": -120.0, "currency": "USD", "category": "Uncategorized"},
            {"date": "2026-05-11", "description": "UNKNOWN_B",
             "amount": -80.0,  "currency": "USD", "category": "Uncategorized"},
            {"date": "2026-05-12", "description": "GROCERIES",
             "amount": -200.0, "currency": "USD", "category": "Groceries"},
            # income row – must NOT be counted
            {"date": "2026-05-15", "description": "SALARY",
             "amount": 3000.0, "currency": "USD", "category": "Uncategorized"},
        ],
    })
    return pid


def _seed_mixed_currency(client, monkeypatch):
    """
    ILS uncategorized spend (-4000 ILS == -1000 USD at USD->ILS 4.0)
    + USD uncategorized spend (-200 USD).
    Total base amount must be 1200 USD, NOT 4200 (raw ILS + raw USD).
    """
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": 4.0}})
    pid = client.get("/api/people").json()[0]["id"]
    client.post("/api/import/commit", json={
        "person_id": pid, "filename": "f2.csv", "file_hash": "h2", "source": "bank",
        "rows": [
            {"date": "2026-05-05", "description": "ILS_SHOP",
             "amount": -4000.0, "currency": "ILS", "category": "Uncategorized"},
            {"date": "2026-05-06", "description": "USD_SHOP",
             "amount": -200.0,  "currency": "USD", "category": "Uncategorized"},
        ],
    })
    return pid


# ---------------------------------------------------------------------------
# tests
# ---------------------------------------------------------------------------

def test_uncategorized_field_present(client, monkeypatch):
    """The overview response must contain the 'uncategorized' key."""
    pid = _seed_uncategorized(client, monkeypatch)
    resp = client.get("/api/overview", params={"person_id": pid, "month": "2026-05"})
    assert resp.status_code == 200
    data = resp.json()
    assert "uncategorized" in data, f"'uncategorized' key missing from overview response: {list(data.keys())}"


def test_uncategorized_count(client, monkeypatch):
    """count = number of expense rows (amount < 0) with Uncategorized category."""
    pid = _seed_uncategorized(client, monkeypatch)
    data = client.get("/api/overview", params={"person_id": pid, "month": "2026-05"}).json()
    # 2 expense rows with category="Uncategorized"; the income row must NOT count
    assert data["uncategorized"]["count"] == 2


def test_uncategorized_amount_usd(client, monkeypatch):
    """amount = USD-base spend for Uncategorized, consistent with by_category."""
    pid = _seed_uncategorized(client, monkeypatch)
    data = client.get("/api/overview", params={"person_id": pid, "month": "2026-05"}).json()
    # 120 + 80 = 200, income row should be netted out by category_totals
    assert data["uncategorized"]["amount"] == data["by_category"].get("Uncategorized", 0.0)
    assert data["uncategorized"]["amount"] == 200.0


def test_uncategorized_amount_uses_usd_base_not_raw(client, monkeypatch):
    """Mixed currencies: amount must be base-summed (USD), not raw original amounts."""
    pid = _seed_mixed_currency(client, monkeypatch)
    data = client.get("/api/overview", params={"person_id": pid, "month": "2026-05"}).json()
    unc = data["uncategorized"]
    # -4000 ILS at rate 4.0 = -1000 USD base + -200 USD = 1200 USD total spend
    assert unc["amount"] == 1200.0, (
        f"Expected 1200.0 (USD base), got {unc['amount']} — raw ILS sum would be 4200"
    )
    assert unc["count"] == 2


def test_uncategorized_amount_scaled_to_display(client, monkeypatch):
    """amount is scaled to display currency (same factor as by_category)."""
    from modules import fx
    pid = _seed_uncategorized(client, monkeypatch)
    # inject a display rate: 1 USD = 3.5 ILS
    fx.upsert_rate(date.today().isoformat(), "USD", "ILS", 3.5)
    data = client.get("/api/overview",
                      params={"person_id": pid, "month": "2026-05", "display": "ILS"}).json()
    # 200 USD base * 3.5 = 700.0
    assert data["uncategorized"]["amount"] == 700.0
    # must match by_category
    assert data["uncategorized"]["amount"] == data["by_category"].get("Uncategorized", 0.0)


def test_uncategorized_zero_when_none(client, monkeypatch):
    """When there are no uncategorized rows, count=0 and amount=0.0."""
    pid = client.get("/api/people").json()[0]["id"]
    client.post("/api/import/commit", json={
        "person_id": pid, "filename": "f3.csv", "file_hash": "h3", "source": "bank",
        "rows": [
            {"date": "2026-05-10", "description": "FOOD",
             "amount": -150.0, "currency": "USD", "category": "Groceries"},
        ],
    })
    data = client.get("/api/overview", params={"person_id": pid, "month": "2026-05"}).json()
    assert data["uncategorized"]["count"] == 0
    assert data["uncategorized"]["amount"] == 0.0


def test_uncategorized_in_empty_state(client, monkeypatch):
    """_empty() path (no transactions): uncategorized must still be present."""
    data = client.get("/api/overview").json()
    assert "uncategorized" in data
    assert data["uncategorized"]["count"] == 0
    assert data["uncategorized"]["amount"] == 0.0
