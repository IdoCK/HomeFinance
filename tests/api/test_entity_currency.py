def test_account_stores_currency(client):
    pid = client.get("/api/people").json()[0]["id"]
    client.post("/api/networth/accounts", json={
        "person_id": pid, "name": "TLV Savings", "kind": "savings",
        "is_asset": True, "balance": 1000.0, "currency": "ILS"})
    acc = client.get("/api/networth", params={"person_id": pid}).json()["accounts"][0]
    assert acc["currency"] == "ILS"
