from modules import database, fx


def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "t.db")
    database.init_db()


def test_usd_passthrough_no_network(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    monkeypatch.setattr(fx, "_http_get_json",
                        lambda url: (_ for _ in ()).throw(AssertionError("network called for USD")))
    assert fx.to_base(3684.08, "USD", "2026-03-13") == 3684.08


def test_non_usd_converts_to_usd(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    fx.upsert_rate("2026-03-13", "USD", "ILS", 4.0)  # 1 USD = 4 ILS
    # 400 ILS / 4 = 100 USD
    assert fx.to_base(400.0, "ILS", "2026-03-13") == 100.0


def test_to_base_fetches_on_miss(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    monkeypatch.setattr(fx, "_http_get_json",
                        lambda url: {"rates": {"ILS": 4.0}})
    assert fx.to_base(400.0, "ILS", "2026-03-13") == 100.0


def test_to_base_none_when_unresolvable(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    monkeypatch.setattr(fx, "_http_get_json",
                        lambda url: (_ for _ in ()).throw(OSError("offline")))
    assert fx.to_base(400.0, "ILS", "2026-03-13") is None


def test_convert_usd_to_display(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    fx.upsert_rate("2026-03-13", "USD", "ILS", 3.5)
    assert fx.convert(100.0, "USD", "2026-03-13") == 100.0
    assert fx.convert(100.0, "ILS", "2026-03-13") == 350.0


def test_resolve_rows_flags_stale(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    monkeypatch.setattr(fx, "_http_get_json",
                        lambda url: (_ for _ in ()).throw(OSError("offline")))
    rows = [{"amount": 100.0, "currency": "USD", "date": "2026-03-13", "amount_base": None},
            {"amount": 400.0, "currency": "ILS", "date": "2026-03-13", "amount_base": None}]
    out = fx.resolve_rows(rows)
    assert out[0]["amount_base"] == 100.0 and not out[0].get("rate_stale")
    assert out[1]["amount_base"] is None and out[1]["rate_stale"] is True
