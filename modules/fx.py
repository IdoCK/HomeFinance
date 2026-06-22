"""Foreign-exchange conversion for the household ledger.

Canonical pivot is USD: every transaction's `amount_base` is in USD, and USD
rows need no conversion at all. Rates live in the `fx_rates` table, one
direction only (base='USD'); the reverse pair is derived as 1/rate.

Privacy: the ONLY outbound network call is `fetch_rate`, and it sends only a
date and a currency pair (no amounts, no personal data). All conversion math is
local. Lookups (`get_rate`) are DB-only and never touch the network.
"""
from modules import database as db

PIVOT = "USD"


def upsert_rate(rate_date, base, quote, rate, source="manual"):
    """Insert/replace one rate row (PK = rate_date, base, quote)."""
    from datetime import datetime
    with db.get_conn() as conn:
        conn.execute(
            """INSERT INTO fx_rates(rate_date, base, quote, rate, source, fetched_at)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(rate_date, base, quote) DO UPDATE SET
                   rate=excluded.rate, source=excluded.source,
                   fetched_at=excluded.fetched_at""",
            (rate_date, base, quote, float(rate), source,
             datetime.now().isoformat(timespec="seconds")))


def _lookup(rate_date, base, quote):
    """Raw DB lookup: exact day else nearest prior. None if nothing on/before."""
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT rate FROM fx_rates WHERE base=? AND quote=? AND rate_date<=? "
            "ORDER BY rate_date DESC LIMIT 1", (base, quote, rate_date)).fetchone()
        return row[0] if row else None


def get_rate(rate_date, base, quote):
    """Rate to multiply `base` by to get `quote`, on `rate_date` (exact day else
    nearest prior business day). DB-only, offline-safe: returns None if absent."""
    if base == quote:
        return 1.0
    direct = _lookup(rate_date, base, quote)
    if direct is not None:
        return direct
    inverse = _lookup(rate_date, quote, base)
    if inverse:
        return 1.0 / inverse
    return None
