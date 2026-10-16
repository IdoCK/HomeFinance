"""Task 1.8 — FX freshness hygiene.

Tests:
  A) POST /fx/refresh chains recompute_amount_base: stale rows are filled.
  B) get_rate_with_age reports correct age (days) for nearest-prior fallback,
     0 for exact-day hit, and flags stale beyond threshold.
"""
import pytest
from datetime import date, timedelta

# ── A: /fx/refresh chains recompute ─────────────────────────────────────────


def test_refresh_chains_recompute_fills_stale_rows(client, monkeypatch):
    """After /fx/refresh with network stubbed to return a rate, stale
    amount_base rows should be recomputed and the response includes
    a 'recomputed' key with updated/stale counts."""
    from modules import fx

    # Stub network to always fail — import the row while offline so amount_base=None
    monkeypatch.setattr(fx, "_http_get_json",
                        lambda url: (_ for _ in ()).throw(OSError("offline")))

    pid = client.get("/api/people").json()[0]["id"]
    client.post("/api/import/commit", json={
        "person_id": pid, "filename": "f.csv", "file_hash": "h1", "source": "bank",
        "rows": [{"date": "2026-04-01", "description": "Offline ILS",
                  "amount": 400.0, "currency": "ILS"}],
    })

    # Verify the DB row has amount_base=NULL (the transactions GET endpoint
    # falls back to the raw amount as a display measure, masking the NULL).
    # We verify by checking the raw DB directly via the database module.
    from modules import database as db
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT amount_base FROM transactions WHERE description='Offline ILS'"
        ).fetchone()
    assert row is not None, "Precondition: ILS row must exist in DB"
    assert row[0] is None, (
        f"Precondition: amount_base should be NULL in DB (got {row[0]})"
    )

    # Now stub network to succeed and call /fx/refresh
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": 4.0}})
    out = client.post("/api/fx/refresh", json={
        "dates": ["2026-04-01"], "base": "USD", "quote": "ILS",
    }).json()

    # Response must include recomputed block
    assert "recomputed" in out, f"Expected 'recomputed' in response, got: {out}"
    assert out["fetched"] == 1
    assert out["failed"] == 0
    assert out["recomputed"]["updated"] >= 1
    assert out["recomputed"]["stale"] == 0

    # The row's amount_base must now be filled in the DB
    txns2 = client.get("/api/transactions", params={"person_id": pid}).json()
    updated_row = next(t for t in txns2 if t["description"] == "Offline ILS")
    assert updated_row["amount_base"] == pytest.approx(100.0), (
        f"Expected 100.0 (400 ILS / 4), got {updated_row['amount_base']}"
    )


def test_refresh_response_still_has_fetched_failed(client, monkeypatch):
    """Existing callers of /fx/refresh must still see fetched/failed keys."""
    from modules import fx
    monkeypatch.setattr(fx, "_http_get_json", lambda url: {"rates": {"ILS": 3.9}})
    out = client.post("/api/fx/refresh", json={
        "dates": ["2026-03-13", "2026-03-14"], "base": "USD", "quote": "ILS",
    }).json()
    assert out["fetched"] == 2
    assert out["failed"] == 0
    assert "recomputed" in out   # new key present even when no stale rows


# ── B: get_rate_with_age ─────────────────────────────────────────────────────


def test_get_rate_with_age_exact_day_returns_age_zero():
    """When a rate exists for exactly the requested date, age is 0 and
    rate_stale_age is False."""
    from modules import fx, database as db
    import importlib
    import tempfile, os, pathlib

    with tempfile.TemporaryDirectory() as tmp:
        db_path = pathlib.Path(tmp) / "test.db"
        # Temporarily redirect DB_PATH
        orig = db.DB_PATH
        db.DB_PATH = db_path
        try:
            db.init_db()
            fx.upsert_rate("2026-04-01", "USD", "ILS", 3.7)
            rate, age_days, stale_age = fx.get_rate_with_age("2026-04-01", "USD", "ILS")
            assert rate == pytest.approx(3.7)
            assert age_days == 0
            assert stale_age is False
        finally:
            db.DB_PATH = orig


def test_get_rate_with_age_prior_fallback_reports_age():
    """When only a prior-dated rate exists (10 days before request), age is 10
    and stale_age is True (beyond the 7-day threshold)."""
    from modules import fx, database as db
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as tmp:
        db_path = pathlib.Path(tmp) / "test2.db"
        orig = db.DB_PATH
        db.DB_PATH = db_path
        try:
            db.init_db()
            rate_date = "2026-04-01"
            request_date = "2026-04-11"  # 10 days later
            fx.upsert_rate(rate_date, "USD", "ILS", 3.8)
            rate, age_days, stale_age = fx.get_rate_with_age(request_date, "USD", "ILS")
            assert rate == pytest.approx(3.8)
            assert age_days == 10
            assert stale_age is True   # 10 > STALE_RATE_DAYS (7)
        finally:
            db.DB_PATH = orig


def test_get_rate_with_age_within_threshold_not_stale():
    """A rate 3 days old is within the 7-day threshold; stale_age is False."""
    from modules import fx, database as db
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as tmp:
        db_path = pathlib.Path(tmp) / "test3.db"
        orig = db.DB_PATH
        db.DB_PATH = db_path
        try:
            db.init_db()
            fx.upsert_rate("2026-04-08", "USD", "ILS", 3.6)
            rate, age_days, stale_age = fx.get_rate_with_age("2026-04-11", "USD", "ILS")
            assert rate == pytest.approx(3.6)
            assert age_days == 3
            assert stale_age is False   # 3 <= STALE_RATE_DAYS (7)
        finally:
            db.DB_PATH = orig


def test_get_rate_with_age_no_rate_returns_none():
    """When no rate exists, get_rate_with_age returns (None, None, None)."""
    from modules import fx, database as db
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as tmp:
        db_path = pathlib.Path(tmp) / "test4.db"
        orig = db.DB_PATH
        db.DB_PATH = db_path
        try:
            db.init_db()
            result = fx.get_rate_with_age("2026-04-11", "USD", "ILS")
            assert result == (None, None, None)
        finally:
            db.DB_PATH = orig


def test_get_rate_with_age_same_currency():
    """Same base==quote returns rate=1.0, age=0, stale_age=False."""
    from modules import fx
    rate, age_days, stale_age = fx.get_rate_with_age("2026-04-11", "USD", "USD")
    assert rate == 1.0
    assert age_days == 0
    assert stale_age is False


def test_get_rate_with_age_inverse_pair():
    """When only the inverse pair (ILS/USD) is stored, age is still computed."""
    from modules import fx, database as db
    import tempfile, pathlib

    with tempfile.TemporaryDirectory() as tmp:
        db_path = pathlib.Path(tmp) / "test5.db"
        orig = db.DB_PATH
        db.DB_PATH = db_path
        try:
            db.init_db()
            # Store ILS->USD (inverse of what we look up)
            fx.upsert_rate("2026-04-01", "ILS", "USD", 0.25)
            rate, age_days, stale_age = fx.get_rate_with_age("2026-04-11", "USD", "ILS")
            assert rate == pytest.approx(4.0)   # 1/0.25
            assert age_days == 10
            assert stale_age is True
        finally:
            db.DB_PATH = orig


def test_stale_rate_days_constant_is_exposed():
    """STALE_RATE_DAYS must be importable from modules.fx."""
    from modules import fx
    assert hasattr(fx, "STALE_RATE_DAYS")
    assert isinstance(fx.STALE_RATE_DAYS, int)
    assert fx.STALE_RATE_DAYS > 0
