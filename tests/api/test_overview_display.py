from datetime import date


def _seed(client, monkeypatch):
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": 4.0}})
    pid = client.get("/api/people").json()[0]["id"]
    m = date.today().strftime("%Y-%m")
    client.post("/api/import/commit", json={
        "person_id": pid, "filename": "f.csv", "file_hash": "h", "source": "bank",
        "rows": [
            {"date": f"{m}-05", "description": "PAY", "amount": 2000.0, "currency": "USD"},
            {"date": f"{m}-06", "description": "STORE", "amount": -500.0, "currency": "USD"},
        ]})
    return pid


def test_overview_usd_unchanged(client, monkeypatch):
    pid = _seed(client, monkeypatch)
    o = client.get("/api/overview", params={"person_id": pid}).json()
    assert o["income"] == 2000.0 and o["spend"] == 500.0


def test_overview_ils_scales_by_today_factor(client, monkeypatch):
    from modules import fx
    pid = _seed(client, monkeypatch)
    fx.upsert_rate(date.today().isoformat(), "USD", "ILS", 3.0)
    o = client.get("/api/overview", params={"person_id": pid, "display": "ILS"}).json()
    assert o["income"] == 6000.0 and o["spend"] == 1500.0   # x3
