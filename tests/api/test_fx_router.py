def test_manual_upsert_and_inspect(client):
    client.put("/api/fx/rates", json={"rate_date": "2026-03-13", "base": "USD",
                                       "quote": "ILS", "rate": 3.6})
    data = client.get("/api/fx/rates").json()
    assert data["count"] == 1
    assert data["rates"][0]["rate"] == 3.6
    assert data["rates"][0]["source"] == "manual"


def test_refresh_fetches_listed_dates(client, monkeypatch):
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": 3.9}})
    out = client.post("/api/fx/refresh", json={"dates": ["2026-03-13", "2026-03-14"]}).json()
    assert out["fetched"] == 2 and out["failed"] == 0
    assert client.get("/api/fx/rates").json()["count"] == 2
