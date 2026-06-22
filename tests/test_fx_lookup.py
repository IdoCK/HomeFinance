from modules import database, fx


def _fresh_db(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DB_PATH", tmp_path / "t.db")
    database.init_db()


def test_same_currency_is_identity(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    assert fx.get_rate("2026-03-13", "USD", "USD") == 1.0


def test_upsert_and_exact_lookup(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    fx.upsert_rate("2026-03-13", "USD", "ILS", 3.60, source="manual")
    assert fx.get_rate("2026-03-13", "USD", "ILS") == 3.60


def test_nearest_prior_business_day(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    fx.upsert_rate("2026-03-13", "USD", "ILS", 3.60)  # Friday
    # Sat/Sun have no row; Saturday lookup carries Friday forward.
    assert fx.get_rate("2026-03-14", "USD", "ILS") == 3.60


def test_inverse_pair_is_derived(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    fx.upsert_rate("2026-03-13", "USD", "ILS", 4.0)
    assert fx.get_rate("2026-03-13", "ILS", "USD") == 0.25  # 1/4


def test_missing_rate_returns_none(tmp_path, monkeypatch):
    _fresh_db(tmp_path, monkeypatch)
    assert fx.get_rate("2026-03-13", "USD", "ILS") is None
