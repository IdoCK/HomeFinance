def test_networth_summary(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.add_account(you, "Checking", "checking", 1, 5000.0)
    db.add_account(you, "Visa", "credit_card", 0, 1200.0)

    data = client.get("/api/networth", params={"person_id": you}).json()
    assert data["summary"] == {"assets": 5000.0, "liabilities": 1200.0, "net": 3800.0}
    assert len(data["accounts"]) == 2


def test_reconcile_ties_out(client, people):
    from modules import database as db
    you = people[0]["id"]
    # A tidy statement: opening 1000, two moves, running balance tracks them.
    db.add_transactions(you, [
        {"date": "2026-05-01", "description": "Open", "amount": -200.0, "category": "x", "source": "bank", "balance": 800.0},
        {"date": "2026-05-02", "description": "Deposit", "amount": 500.0, "category": "x", "source": "bank", "balance": 1300.0},
    ])
    r = client.get("/api/networth/reconcile", params={"person_id": you}).json()
    assert r["reconcilable"] is True
    assert r["ok"] is True
    assert r["begin"] == 1000.0 and r["end"] == 1300.0


def test_reconcile_not_possible_without_balances(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.add_transactions(you, [
        {"date": "2026-05-01", "description": "Card", "amount": -50.0, "category": "x", "source": "credit_card"},
    ])
    r = client.get("/api/networth/reconcile", params={"person_id": you}).json()
    assert r["reconcilable"] is False


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


def test_networth_joint_split_per_person(client, people):
    from modules import database as db
    ido, aviv = people[0]["id"], people[1]["id"]
    db.add_account(ido, "Ido Checking", "checking", 1, 1000.0)
    db.add_account(aviv, "Aviv Savings", "savings", 1, 4000.0)
    db.add_account(None, "Joint House", "property", 1, 200000.0)
    # Joint: split present, one row per owner (+ Shared), nets sum to summary.net
    d = client.get("/api/networth").json()
    assert d["split"] is not None
    by_name = {r["name"]: r["net"] for r in d["split"]}
    assert by_name[people[0]["name"]] == 1000.0
    assert by_name[people[1]["name"]] == 4000.0
    assert by_name["Shared"] == 200000.0
    assert round(sum(r["net"] for r in d["split"]), 2) == round(d["summary"]["net"], 2)
    # Single persona: no split
    d2 = client.get("/api/networth", params={"person_id": ido}).json()
    assert d2["split"] is None
