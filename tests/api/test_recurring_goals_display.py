from datetime import date


def test_goals_scale(client, monkeypatch):
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": 4.0}})
    pid = client.get("/api/people").json()[0]["id"]
    client.post("/api/goals", json={"person_id": pid, "name": "Car", "target_amount": 10000.0})
    fx.upsert_rate(date.today().isoformat(), "USD", "ILS", 3.0)
    g = client.get("/api/goals", params={"person_id": pid, "display": "ILS"}).json()
    car = next(x for x in g if x["name"] == "Car")
    assert car["target_amount"] == 30000.0
