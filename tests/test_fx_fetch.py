from modules import database, fx


def test_url_carries_only_date_and_currencies():
    url = fx.frankfurter_url("2026-03-13", "USD", "ILS")
    assert url == "https://api.frankfurter.dev/v1/2026-03-13?base=USD&symbols=ILS"
    # Privacy invariant: nothing but the date + currency codes is present.
    for forbidden in ("amount", "3684", "ILLUMINA", "person", "Ido", "Aviv"):
        assert forbidden not in url


def test_fetch_rate_caches_and_returns(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "t.db")
    database.init_db()

    calls = []
    def fake_http(url):
        calls.append(url)
        return {"base": "USD", "date": "2026-03-13", "rates": {"ILS": 3.66}}
    monkeypatch.setattr(fx, "_http_get_json", fake_http)

    assert fx.fetch_rate("2026-03-13", "USD", "ILS") == 3.66
    # Cached now: a second get_rate must NOT trigger another fetch.
    assert fx.get_rate("2026-03-13", "USD", "ILS") == 3.66
    assert len(calls) == 1


def test_fetch_rate_returns_none_on_network_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "t.db")
    database.init_db()
    def boom(url):
        raise OSError("offline")
    monkeypatch.setattr(fx, "_http_get_json", boom)
    assert fx.fetch_rate("2026-03-13", "USD", "ILS") is None
