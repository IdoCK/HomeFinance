def _commit(client, monkeypatch, rows):
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": 4.0}})
    pid = client.get("/api/people").json()[0]["id"]
    client.post("/api/import/commit", json={
        "person_id": pid, "filename": "f.csv", "file_hash": "h", "source": "bank", "rows": rows})
    return pid


def test_default_display_is_usd_passthrough(client, monkeypatch):
    pid = _commit(client, monkeypatch, [
        {"date": "2026-03-13", "description": "PAY", "amount": 1000.0, "currency": "USD"}])
    row = client.get("/api/transactions", params={"person_id": pid}).json()[0]
    assert row["original_amount"] == 1000.0
    assert row["original_currency"] == "USD"
    assert row["amount"] == 1000.0          # display == base for USD
    assert row["rate_stale"] is False


def test_ils_display_converts_each_row_at_its_date(client, monkeypatch):
    from modules import fx
    pid = _commit(client, monkeypatch, [
        {"date": "2026-03-13", "description": "PAY", "amount": 1000.0, "currency": "USD"}])
    # 1 USD = 3.5 ILS today-of-row
    fx.upsert_rate("2026-03-13", "USD", "ILS", 3.5)
    row = client.get("/api/transactions", params={"person_id": pid, "display": "ILS"}).json()[0]
    assert row["original_amount"] == 1000.0 and row["original_currency"] == "USD"
    assert row["amount"] == 3500.0          # 1000 USD * 3.5
