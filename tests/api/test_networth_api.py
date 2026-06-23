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


def test_account_history_returns_snapshots_oldest_first(client, people):
    from modules import database as db
    you = people[0]["id"]
    aid = db.add_account(you, "Brokerage", "investment", 1, 10000.0)  # snapshot today
    db.write_snapshot(aid, "2026-01-01", 8000.0)
    db.write_snapshot(aid, "2026-03-01", 9000.0)

    d = client.get(f"/api/networth/accounts/{aid}/history").json()
    snaps = d["snapshots"]
    assert [s["date"] for s in snaps][:2] == ["2026-01-01", "2026-03-01"]
    assert snaps[0]["balance"] == 8000.0
    # the create-time snapshot (today) sorts last
    assert snaps[-1]["balance"] == 10000.0


def test_account_history_empty_for_unknown_account(client, people):
    d = client.get("/api/networth/accounts/9999/history").json()
    assert d == {"snapshots": []}


def test_record_manual_snapshot_sets_balance_and_history(client, people):
    from modules import database as db
    you = people[0]["id"]
    aid = db.add_account(you, "401k", "investment", 1, 0.0)
    r = client.post(f"/api/networth/accounts/{aid}/snapshot",
                    json={"date": "2026-03-31", "balance": 42000})
    assert r.status_code == 200
    nw = client.get("/api/networth", params={"person_id": you}).json()
    assert next(a for a in nw["accounts"] if a["id"] == aid)["balance"] == 42000.0
    hist = client.get(f"/api/networth/accounts/{aid}/history").json()["snapshots"]
    assert {"date": "2026-03-31", "balance": 42000.0} in hist


def test_populate_month_end_balances_from_statements(client, people):
    from modules import database as db
    you = people[0]["id"]
    fh = "stmt-hash-1"
    db.add_transactions(you, [
        {"date": "2026-04-10", "description": "x", "amount": -100.0, "category": "c", "source": "bank", "balance": 900.0},
        {"date": "2026-04-28", "description": "y", "amount": -50.0, "category": "c", "source": "bank", "balance": 850.0},
        {"date": "2026-05-15", "description": "z", "amount": -50.0, "category": "c", "source": "bank", "balance": 800.0},
    ], file_hash=fh)
    db.record_import(you, fh, "april-may.csv", 3, "2026-06-01T00:00:00")
    aid = db.add_account(you, "Checking", "checking", 1, 0.0)

    imps = client.get(f"/api/networth/accounts/{aid}/imports").json()["imports"]
    assert any(i["file_hash"] == fh and i["filename"] == "april-may.csv" for i in imps)

    r = client.post(f"/api/networth/accounts/{aid}/populate-from-statements",
                    json={"file_hashes": [fh]}).json()
    assert r["recorded"] == 2  # April month-end (Apr 28) + May month-end (May 15)
    hist = {s["date"]: s["balance"] for s in
            client.get(f"/api/networth/accounts/{aid}/history").json()["snapshots"]}
    assert hist["2026-04-28"] == 850.0
    assert hist["2026-05-15"] == 800.0
    nw = client.get("/api/networth", params={"person_id": you}).json()
    assert next(a for a in nw["accounts"] if a["id"] == aid)["balance"] == 800.0  # latest month-end


def test_populate_from_card_feed_records_nothing(client, people):
    from modules import database as db
    you = people[0]["id"]
    fh = "card-hash"
    db.add_transactions(you, [
        {"date": "2026-04-10", "description": "card", "amount": -30.0, "category": "c", "source": "credit_card"},
    ], file_hash=fh)
    db.record_import(you, fh, "visa.csv", 1, "2026-06-01T00:00:00")
    aid = db.add_account(you, "Visa", "credit_card", 0, 0.0)
    r = client.post(f"/api/networth/accounts/{aid}/populate-from-statements",
                    json={"file_hashes": [fh]}).json()
    assert r["recorded"] == 0  # no running balance to derive month-ends from


def test_snapshot_unknown_account_404(client, people):
    r = client.post("/api/networth/accounts/9999/snapshot", json={"date": "2026-01-01", "balance": 1})
    assert r.status_code == 404


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
