from datetime import date


def test_networth_scales_balances(client, monkeypatch):
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": 4.0}})
    pid = client.get("/api/people").json()[0]["id"]
    client.post("/api/networth/accounts", json={
        "person_id": pid, "name": "Checking", "kind": "checking", "is_asset": True, "balance": 1000.0})
    fx.upsert_rate(date.today().isoformat(), "USD", "ILS", 3.0)

    usd = client.get("/api/networth", params={"person_id": pid}).json()
    assert usd["summary"]["assets"] == 1000.0
    ils = client.get("/api/networth", params={"person_id": pid, "display": "ILS"}).json()
    assert ils["summary"]["assets"] == 3000.0
    assert ils["accounts"][0]["original_balance"] == 1000.0


def test_budgets_scale(client, monkeypatch):
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": 4.0}})
    pid = client.get("/api/people").json()[0]["id"]
    m = date.today().strftime("%Y-%m")
    client.post("/api/import/commit", json={
        "person_id": pid, "filename": "f.csv", "file_hash": "h", "source": "bank",
        "rows": [{"date": f"{m}-05", "description": "STORE", "amount": -200.0,
                  "currency": "USD", "category": "Shopping"}]})
    client.put("/api/budgets", json={"person_id": pid, "category": "Shopping", "amount": 500.0})
    fx.upsert_rate(date.today().isoformat(), "USD", "ILS", 2.0)
    b = client.get("/api/budgets", params={"person_id": pid, "display": "ILS"}).json()
    row = next(r for r in b if r["category"] == "Shopping")
    assert row["spent"] == 400.0 and row["budget"] == 1000.0   # x2
