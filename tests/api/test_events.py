def test_event_crud_and_tagging(client, people):
    from modules import database as db
    you = people[0]["id"]
    db.add_transactions(you, [
        {"date": "2026-05-01", "description": "Flight", "amount": -400.0, "category": "Travel", "source": "card"},
        {"date": "2026-05-02", "description": "Hotel", "amount": -600.0, "category": "Travel", "source": "card"},
    ])
    ids = [t["id"] for t in client.get("/api/transactions", params={"person_id": you}).json()]

    eid = client.post("/api/events", json={"person_id": you, "name": "Hawaii", "kind": "trip"}).json()["id"]

    client.put(f"/api/events/{eid}/transactions", json={"transaction_ids": ids})
    assert set(client.get(f"/api/events/{eid}/transactions").json()) == set(ids)

    events = client.get("/api/events", params={"person_id": you}).json()
    ev = next(e for e in events if e["id"] == eid)
    assert ev["name"] == "Hawaii"
    assert ev["txn_count"] == 2
    assert ev["total"] == -1000.0

    client.delete(f"/api/events/{eid}")
    assert all(e["id"] != eid for e in client.get("/api/events", params={"person_id": you}).json())


def test_events_empty(client, people):
    assert client.get("/api/events", params={"person_id": people[0]["id"]}).json() == []
