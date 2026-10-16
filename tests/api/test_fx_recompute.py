def test_recompute_fills_base_after_rate_added(client, monkeypatch):
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json",
                        lambda url: (_ for _ in ()).throw(OSError("offline")))
    pid = client.get("/api/people").json()[0]["id"]
    # Commit an ILS row while offline -> amount_base unresolved (None).
    client.post("/api/import/commit", json={
        "person_id": pid, "filename": "f.csv", "file_hash": "h", "source": "bank",
        "rows": [{"date": "2026-03-13", "description": "TLV", "amount": 400.0, "currency": "ILS"}]})
    # Provide the rate, then recompute.
    fx.upsert_rate("2026-03-13", "USD", "ILS", 4.0)
    out = client.post("/api/fx/recompute").json()
    assert out["updated"] >= 1 and out["stale"] == 0
    row = next(t for t in client.get("/api/transactions", params={"person_id": pid}).json()
               if t["description"] == "TLV")
    assert row["amount_base"] == 100.0   # 400 ILS / 4
