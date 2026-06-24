"""API tests for GET /networth/growth — trailing-12m, CAGR, FIRE, runway."""


def _seed_trend(you):
    """One investment account whose snapshots span a full year: 100k -> 130k."""
    from modules import database as db
    acct = db.add_account(you, "Brokerage", "investment", 1, 130000.0, "USD")
    db.write_snapshot(acct, "2025-06-01", 100000.0)
    db.write_snapshot(acct, "2025-12-01", 110000.0)
    db.write_snapshot(acct, "2026-06-01", 130000.0)
    return acct


def test_growth_trailing_cagr_and_fire(client, people):
    from modules import database as db
    you = people[0]["id"]
    _seed_trend(you)
    # A complete May with $3000 of expenses -> $36k/yr -> $900k FIRE number.
    db.add_transactions(you, [
        {"date": "2026-05-01", "description": "Rent", "amount": -3000.0, "category": "Housing", "source": "bank"},
        {"date": "2026-05-31", "description": "Paycheck", "amount": 5000.0, "category": "Income", "source": "bank"},
    ])

    d = client.get("/api/networth/growth", params={"person_id": you}).json()
    assert d["current_net"] == 130000.0
    # Trailing 12m: 130k now vs 100k a year ago.
    assert d["trailing_abs"] == 30000.0
    assert round(d["trailing_pct"], 1) == 30.0
    # CAGR over the snapshot span (100k -> 130k). add_account writes a today-
    # dated snapshot, so the span runs a little over a year and the annualized
    # rate sits just under the raw 30% — assert a tight band, not a fragile const.
    assert d["span_years"] >= 1.0
    assert 0.27 < d["cagr"] < 0.31
    # FIRE: 25 x $36k annual expenses.
    assert d["fire_number"] == 900000.0
    assert round(d["pct_to_fire"], 4) == round(130000 / 900000, 4)
    # No recurring charges seeded -> no committed burn -> runway unknown.
    assert d["runway_months"] is None


def test_growth_runway_from_committed_bills(client, people):
    from modules import database as db
    you = people[0]["id"]
    _seed_trend(you)
    # Six monthly subscription charges so the engine detects a committed bill.
    db.add_transactions(you, [
        {"date": f"2026-{m:02d}-10", "description": "NETFLIX.COM", "amount": -15.99,
         "category": "Subscriptions", "source": "credit_card"}
        for m in range(1, 7)
    ])

    d = client.get("/api/networth/growth", params={"person_id": you}).json()
    assert d["monthly_committed"] > 0
    # Runway = current net worth / monthly committed burn.
    assert d["runway_months"] == round(d["current_net"] / d["monthly_committed"], 1)


def test_growth_scales_money_to_display_currency(client, people):
    from datetime import date
    from modules import database as db
    from modules import fx
    you = people[0]["id"]
    _seed_trend(you)
    fx.upsert_rate(date.today().isoformat(), "USD", "ILS", 3.0)
    usd = client.get("/api/networth/growth", params={"person_id": you}).json()
    ils = client.get("/api/networth/growth", params={"person_id": you, "display": "ILS"}).json()
    # Ratios (CAGR, trailing_pct) are currency-invariant; abs money fields scale.
    assert ils["trailing_pct"] == usd["trailing_pct"]
    assert ils["cagr"] == usd["cagr"]
    if usd["trailing_abs"] and ils["trailing_abs"]:
        assert ils["trailing_abs"] != usd["trailing_abs"]


def test_growth_empty_when_no_data(client, people):
    d = client.get("/api/networth/growth", params={"person_id": people[0]["id"]}).json()
    assert d["current_net"] == 0.0
    assert d["trailing_abs"] is None
    assert d["cagr"] is None
    assert d["fire_number"] is None
