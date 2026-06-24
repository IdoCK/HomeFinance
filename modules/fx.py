"""Foreign-exchange conversion for the household ledger.

Canonical pivot is USD: every transaction's `amount_base` is in USD, and USD
rows need no conversion at all. Rates live in the `fx_rates` table, one
direction only (base='USD'); the reverse pair is derived as 1/rate.

Privacy: the ONLY outbound network call is `fetch_rate`, and it sends only a
date and a currency pair (no amounts, no personal data). All conversion math is
local. Lookups (`get_rate`) are DB-only and never touch the network.
"""
import json
import urllib.request
from datetime import date as _date

from modules import database as db

PIVOT = "USD"

FRANKFURTER_BASE = "https://api.frankfurter.dev/v1"

# Number of days a nearest-prior fallback rate may be older than the requested
# date before it is considered stale (used by get_rate_with_age).
STALE_RATE_DAYS = 7


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


def _lookup_with_date(rate_date, base, quote):
    """Like _lookup but also returns the actual rate_date stored.
    Returns (rate, actual_rate_date) or (None, None)."""
    with db.get_conn() as conn:
        row = conn.execute(
            "SELECT rate, rate_date FROM fx_rates WHERE base=? AND quote=? AND rate_date<=? "
            "ORDER BY rate_date DESC LIMIT 1", (base, quote, rate_date)).fetchone()
        if row is None:
            return None, None
        return row[0], row[1]


def get_rate_with_age(rate_date, base, quote):
    """Like get_rate but also returns the age in days between the requested
    date and the rate_date actually used, plus a boolean indicating whether
    that age exceeds STALE_RATE_DAYS.

    Returns a 3-tuple: (rate, age_days, rate_stale_age).
    - If base == quote: (1.0, 0, False).
    - If no rate found:  (None, None, None).
    - age_days == 0 means the exact requested date was found.
    - rate_stale_age is True when age_days > STALE_RATE_DAYS.

    DB-only, offline-safe — never touches the network.
    """
    from datetime import date as _date_cls
    if base == quote:
        return 1.0, 0, False

    rate, actual_date = _lookup_with_date(rate_date, base, quote)
    if rate is None:
        # Try the inverse pair
        rate, actual_date = _lookup_with_date(rate_date, quote, base)
        if rate is not None:
            rate = 1.0 / rate
        else:
            return None, None, None

    # Compute age in calendar days
    req = _date_cls.fromisoformat(rate_date)
    used = _date_cls.fromisoformat(actual_date)
    age_days = (req - used).days
    return rate, age_days, age_days > STALE_RATE_DAYS


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


def frankfurter_url(rate_date, base, quote):
    """Build the rate-request URL. Carries ONLY the date and currency pair —
    no amounts or personal data (the data-minimization invariant)."""
    return f"{FRANKFURTER_BASE}/{rate_date}?base={base}&symbols={quote}"


def _http_get_json(url):
    """Single GET → parsed JSON. Isolated so tests can stub the network."""
    req = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


def fetch_rate(rate_date, base, quote):
    """Fetch one rate from Frankfurter (ECB data), cache it, return it.

    The only network path in the app. Sends only (date, base, quote). On any
    failure returns None and never raises — the caller flags the row instead.
    Frankfurter returns the nearest prior business day for weekends/holidays;
    we store the rate under the REQUESTED date so repeat lookups hit the cache.
    """
    if base == quote:
        return 1.0
    try:
        data = _http_get_json(frankfurter_url(rate_date, base, quote))
        rate = data.get("rates", {}).get(quote)
        if rate is None:
            return None
        upsert_rate(rate_date, base, quote, float(rate), source="frankfurter")
        return float(rate)
    except Exception:
        return None


def _rate_or_fetch(on_date, base, quote):
    """Cached rate, else one fetch, else None. Offline-safe."""
    r = get_rate(on_date, base, quote)
    if r is not None:
        return r
    return fetch_rate(on_date, base, quote)


def to_base(amount, currency, on_date):
    """Original amount in `currency` -> USD on `on_date`. USD passes through
    untouched (no lookup, no network). None if no rate could be resolved."""
    if amount is None:
        return None
    if currency == PIVOT:
        return amount
    rate = _rate_or_fetch(on_date, PIVOT, currency)  # USD->currency (quote per USD)
    if not rate:
        return None
    return amount / rate


def convert(amount_base_usd, display, on_date=None):
    """USD base -> display currency at `on_date` (today if None). USD passes
    through. None if the rate is unavailable."""
    if amount_base_usd is None:
        return None
    if display == PIVOT:
        return amount_base_usd
    on = on_date or _date.today().isoformat()
    rate = _rate_or_fetch(on, PIVOT, display)
    if not rate:
        return None
    return amount_base_usd * rate


def display_factor(display, on_date=None):
    """USD -> display multiplier for `on_date` (today if None). 1.0 for USD with
    no lookup/network. None if the rate is unavailable (offline + uncached)."""
    if display == PIVOT:
        return 1.0
    on = on_date or _date.today().isoformat()
    return _rate_or_fetch(on, PIVOT, display)


def base_txns(txns):
    """Copies with `amount` set to the USD base, so analytics sum one currency."""
    out = []
    for t in txns:
        base = t.get("amount_base")
        out.append({**t, "amount": base if base is not None else t.get("amount")})
    return out


def resolve_rows(rows):
    """Fill `amount_base` (USD) for rows where it's None; set rate_stale=True
    where conversion failed. Mutates and returns rows."""
    for r in rows:
        if r.get("amount_base") is not None:
            continue
        base = to_base(r.get("amount"), r.get("currency", PIVOT), r.get("date"))
        if base is None:
            r["amount_base"] = None
            r["rate_stale"] = True
        else:
            r["amount_base"] = base
            r["rate_stale"] = False
    return rows
