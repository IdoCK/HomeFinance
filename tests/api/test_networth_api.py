def test_networth_summary(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.add_account(you, "Checking", "checking", 1, 5000.0)
    db.add_account(you, "Visa", "credit_card", 0, 1200.0)

    data = client.get("/api/networth", params={"person_id": you}).json()
    assert data["summary"] == {"assets": 5000.0, "liabilities": 1200.0, "net": 3800.0}
    assert len(data["accounts"]) == 2


def test_add_account_via_api(client, people):
    you = people[0]["id"]
    r = client.post("/api/networth/accounts", json={
        "person_id": you, "name": "Vanguard", "kind": "investment",
        "is_asset": True, "balance": 25000})
    assert r.status_code == 200
    data = client.get("/api/networth", params={"person_id": you}).json()
    assert any(a["name"] == "Vanguard" for a in data["accounts"])
    assert data["summary"]["assets"] == 25000.0


def test_update_account_balance_via_api(client, people):
    from modules import database as db
    you = people[0]["id"]
    aid = db.add_account(you, "Savings", "savings", 1, 1000.0)
    r = client.patch(f"/api/networth/accounts/{aid}", json={"balance": 1500})
    assert r.status_code == 200
    data = client.get("/api/networth", params={"person_id": you}).json()
    assert data["summary"]["net"] == 1500.0


def test_delete_account_via_api(client, people):
    from modules import database as db
    you = people[0]["id"]
    aid = db.add_account(you, "Temp", "other", 1, 100.0)
    client.delete(f"/api/networth/accounts/{aid}")
    data = client.get("/api/networth", params={"person_id": you}).json()
    assert data["accounts"] == []


def test_trend_and_delta(client, people):
    from modules import database as db
    you = people[0]["id"]
    aid = db.add_account(you, "Brokerage", "investment", 1, 10000.0)  # snapshot today
    db.write_snapshot(aid, "2026-01-01", 8000.0)                       # older snapshot

    data = client.get("/api/networth", params={"person_id": you}).json()
    assert len(data["trend"]) == 2
    assert data["trend"][0]["net"] == 8000.0
    assert data["delta"] == 2000.0  # current net 10000 - prior trend date 8000
