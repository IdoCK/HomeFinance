"""Global display rate — the single USD->quote rate the currency toggle uses.

The `client` fixture clears the seeded rate, so these start from a clean table.
"""


def test_display_rate_absent_then_set(client):
    # No rate set yet (fixture cleared the seed).
    r = client.get("/api/fx/display-rate", params={"quote": "ILS"}).json()
    assert r["rate"] is None

    # Manual set applies globally.
    out = client.put("/api/fx/display-rate", json={"quote": "ILS", "rate": 3.55}).json()
    assert out["ok"] is True
    got = client.get("/api/fx/display-rate", params={"quote": "ILS"}).json()
    assert got["rate"] == 3.55
    assert got["source"] == "manual"


def test_seed_fills_display_rate_once_and_is_idempotent(client):
    from modules import database as db

    db.seed_fx_display_rate()
    r = client.get("/api/fx/display-rate", params={"quote": "ILS"}).json()
    assert r["rate"] == db.FX_SEED_USD_ILS
    assert r["source"] == "seed"

    # A manual override must not be clobbered by a later seed.
    client.put("/api/fx/display-rate", json={"quote": "ILS", "rate": 4.1})
    db.seed_fx_display_rate()
    r2 = client.get("/api/fx/display-rate", params={"quote": "ILS"}).json()
    assert r2["rate"] == 4.1
    assert r2["source"] == "manual"


def test_display_rate_converts_overview_uniformly(client):
    """Every overview figure scales by the manually set display rate."""
    pid = client.get("/api/people").json()[0]["id"]
    client.post("/api/import/commit", json={
        "person_id": pid, "filename": "f.csv", "file_hash": "h1", "source": "bank",
        "rows": [
            {"date": "2026-03-01", "description": "Paycheck", "amount": 1000.0, "currency": "USD"},
            {"date": "2026-03-05", "description": "Rent", "amount": -400.0, "currency": "USD"},
        ],
    })
    client.put("/api/fx/display-rate", json={"quote": "ILS", "rate": 3.5})

    usd = client.get("/api/overview", params={"person_id": pid, "month": "2026-03", "display": "USD"}).json()
    ils = client.get("/api/overview", params={"person_id": pid, "month": "2026-03", "display": "ILS"}).json()
    assert ils["income"] == round(usd["income"] * 3.5, 2)
    assert ils["spend"] == round(usd["spend"] * 3.5, 2)


def test_refresh_display_rate_stores_fetched_value(client, monkeypatch):
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": 3.9}})
    out = client.post("/api/fx/display-rate/refresh", json={"quote": "ILS"}).json()
    assert out["ok"] is True
    assert out["rate"] == 3.9
    got = client.get("/api/fx/display-rate", params={"quote": "ILS"}).json()
    assert got["rate"] == 3.9
    assert got["source"] == "frankfurter"


def test_refresh_display_rate_offline_returns_not_ok(client, monkeypatch):
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json",
                        lambda url: (_ for _ in ()).throw(OSError("offline")))
    out = client.post("/api/fx/display-rate/refresh", json={"quote": "ILS"}).json()
    assert out["ok"] is False
    assert out["rate"] is None
