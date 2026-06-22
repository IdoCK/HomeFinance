# Uses the shared client fixture in tests/api/conftest.py.

def test_commit_writes_currency_and_usd_base(client, monkeypatch):
    from modules import fx
    # No real network: stub the fetcher (USD rows shouldn't call it anyway).
    monkeypatch.setattr(fx, "_http_get_json",
                        lambda url: {"rates": {"ILS": 4.0}})
    people = client.get("/api/people").json()
    pid = people[0]["id"]

    body = {
        "person_id": pid, "filename": "boa.csv", "file_hash": "h1", "source": "bank",
        "rows": [
            {"date": "2026-03-13", "description": "ILLUMINA PAYROLL", "amount": 3684.08,
             "currency": "USD", "currency_source": "person_default"},
            {"date": "2026-03-13", "description": "SUPERMARKET TLV", "amount": 400.0,
             "currency": "ILS", "currency_source": "cell_symbol"},
        ],
    }
    assert client.post("/api/import/commit", json=body).json()["imported"] == 2

    txns = client.get("/api/transactions", params={"person_id": pid}).json()
    usd = next(t for t in txns if "ILLUMINA" in t["description"])
    ils = next(t for t in txns if "SUPERMARKET" in t["description"])
    assert usd["currency"] == "USD" and usd["amount_base"] == 3684.08   # passthrough
    assert ils["currency"] == "ILS" and ils["amount_base"] == 100.0     # 400/4
