from modules import database, fx


def _db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "t.db")
    database.init_db()


def test_usd_factor_is_one_no_network(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    monkeypatch.setattr(fx, "_http_get_json",
                        lambda url: (_ for _ in ()).throw(AssertionError("no network for USD")))
    assert fx.display_factor("USD") == 1.0


def test_ils_factor_uses_today_rate(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    from datetime import date
    fx.upsert_rate(date.today().isoformat(), "USD", "ILS", 3.7)
    assert fx.display_factor("ILS") == 3.7


def test_base_txns_swaps_amount_to_base(tmp_path, monkeypatch):
    _db(tmp_path, monkeypatch)
    rows = [{"amount": 400.0, "amount_base": 100.0, "currency": "ILS"},
            {"amount": 50.0, "amount_base": None, "currency": "USD"}]
    out = fx.base_txns(rows)
    assert out[0]["amount"] == 100.0      # uses base
    assert out[1]["amount"] == 50.0       # falls back to amount
    assert rows[0]["amount"] == 400.0     # original not mutated
