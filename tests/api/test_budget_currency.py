"""Budget caps must be converted from their stored currency to USD before pacing.

Regression guard: a budget stored as ₪1000 (ILS) should be paced against
~$270 USD (at rate USD->ILS 3.7), NOT against $1000. The stored amount and
txns must be compared in the same currency (USD base) — the same invariant
the Overview and Analysis routers already uphold.
"""
from datetime import date

TODAY = date.today().isoformat()

# Deterministic rate: 1 USD = 3.7 ILS → ₪1000 = 1000/3.7 ≈ 270.27 USD
ILS_RATE = 3.7
ILS_BUDGET = 1000.0
ILS_BUDGET_IN_USD = round(ILS_BUDGET / ILS_RATE, 2)  # ≈ 270.27


def _seed(client, monkeypatch):
    """Seed a USD spend transaction and an ILS-denominated budget."""
    from modules import fx
    # Patch network so to_base can resolve USD->ILS without hitting the net
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": ILS_RATE}})

    pid = client.get("/api/people").json()[0]["id"]

    # A $200 USD grocery spend (already in USD base)
    from modules import database as db
    db.add_transactions(pid, [
        {"date": TODAY, "description": "Supermarket", "amount": -200.0,
         "currency": "USD", "category": "Groceries", "source": "card"},
    ])

    # Budget: ₪1000 ILS
    db.set_budget(pid, "Groceries", ILS_BUDGET, "ILS")

    return pid


def test_ils_budget_paced_against_usd_equivalent(client, monkeypatch):
    """The budget amount shown must reflect the USD value of ₪1000, not 1000."""
    pid = _seed(client, monkeypatch)

    rows = client.get("/api/budgets", params={"person_id": pid}).json()
    g = next(b for b in rows if b["category"] == "Groceries")

    # The budget field must be the USD-converted amount, not the raw ILS amount
    # ₪1000 / 3.7 ≈ 270.27 USD — allow ±0.05 for rounding
    assert abs(g["budget"] - ILS_BUDGET_IN_USD) < 0.05, (
        f"Expected budget ~{ILS_BUDGET_IN_USD} USD, got {g['budget']} "
        f"(raw ILS amount would be {ILS_BUDGET})"
    )
    # Spend must remain USD: $200
    assert g["spent"] == 200.0
    # $200 spent against ~$270 cap → on_track or ahead (definitely NOT over)
    assert g["status"] != "over", "Should not be 'over' when $200 < $270 cap"


def test_usd_budget_unchanged(client, monkeypatch):
    """A budget stored in USD must pass through unaffected — no double-conversion."""
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": ILS_RATE}})

    pid = client.get("/api/people").json()[0]["id"]
    from modules import database as db
    db.add_transactions(pid, [
        {"date": TODAY, "description": "Store", "amount": -50.0,
         "currency": "USD", "category": "Shopping", "source": "card"},
    ])
    db.set_budget(pid, "Shopping", 300.0, "USD")

    rows = client.get("/api/budgets", params={"person_id": pid}).json()
    g = next(b for b in rows if b["category"] == "Shopping")

    # USD budget must be 300.0 exactly — no conversion applied
    assert g["budget"] == 300.0
    assert g["spent"] == 50.0


def test_ils_budget_display_ils_does_not_double_convert(client, monkeypatch):
    """When display=ILS, the pipeline is: ILS_cap -> USD base -> ILS display.
    Net result = original ILS cap. Verify no double-conversion at the display step."""
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": ILS_RATE}})
    # Seed a today rate so display_factor also resolves
    fx.upsert_rate(TODAY, "USD", "ILS", ILS_RATE)

    pid = client.get("/api/people").json()[0]["id"]
    from modules import database as db
    db.add_transactions(pid, [
        {"date": TODAY, "description": "Market", "amount": -200.0,
         "currency": "USD", "category": "Groceries", "source": "card"},
    ])
    db.set_budget(pid, "Groceries", ILS_BUDGET, "ILS")

    rows = client.get("/api/budgets",
                      params={"person_id": pid, "display": "ILS"}).json()
    g = next(b for b in rows if b["category"] == "Groceries")

    # USD base (270.27) * ILS_RATE (3.7) ≈ 1000.0 — back to original ILS cap
    assert abs(g["budget"] - ILS_BUDGET) < 1.0, (
        f"With display=ILS the budget should round-trip to ~{ILS_BUDGET}, got {g['budget']}"
    )


def test_missing_rate_degrades_gracefully_not_zero_cap(client, monkeypatch):
    """When to_base returns None (no rate for exotic currency/date), the budget
    must NOT be silently zeroed.  The cap must stay non-zero (falls back to the
    stored amount) and the row must carry rate_stale=True so the UI can warn.

    Regression: previously None → 0 cap → budget always 'on_track', invisible.
    """
    from modules import fx
    # Simulate a completely unknown currency: to_base always returns None.
    monkeypatch.setattr(fx, "_http_get_json",
                        lambda url: {"rates": {}})  # no rates at all

    pid = client.get("/api/people").json()[0]["id"]
    from modules import database as db

    EXOTIC_AMOUNT = 500.0  # stored cap in some exotic currency with no rate
    EXOTIC_CURRENCY = "XYZ"

    # Seed a spend that exceeds the exotic cap.  If the cap were zeroed the
    # status would never be 'over'; with the fallback cap (500) it should be.
    db.add_transactions(pid, [
        {"date": TODAY, "description": "Exotic Shop", "amount": -600.0,
         "currency": "USD", "category": "Travel", "source": "card"},
    ])
    db.set_budget(pid, "Travel", EXOTIC_AMOUNT, EXOTIC_CURRENCY)

    rows = client.get("/api/budgets", params={"person_id": pid}).json()
    g = next(b for b in rows if b["category"] == "Travel")

    # Cap must NOT be zero — a zero cap makes status always 'on_track'.
    assert g["budget"] > 0, (
        f"budget cap must be non-zero when rate is missing, got {g['budget']}"
    )
    # The fallback cap is the stored amount itself (500).
    assert abs(g["budget"] - EXOTIC_AMOUNT) < 0.01, (
        f"Expected fallback cap {EXOTIC_AMOUNT}, got {g['budget']}"
    )
    # rate_stale flag must be present and True.
    assert g.get("rate_stale") is True, (
        f"Expected rate_stale=True on the row, got {g.get('rate_stale')!r}"
    )
    # With $600 spend against a $500 fallback cap the status must be 'over'.
    assert g["status"] == "over", (
        f"Expected status 'over' ($600 spent > $500 cap), got {g['status']!r}"
    )
