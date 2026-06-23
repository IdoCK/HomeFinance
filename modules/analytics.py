"""Compute the numbers the dashboard charts and the AI insights both rely on."""

import json
import statistics
from datetime import date, timedelta
import pandas as pd

from .keywords import keyword_from_desc


def _df(transactions):
    df = pd.DataFrame(transactions)
    if df.empty:
        return df
    # Drop rows the user excluded from calculations (e.g. credit-card payments).
    if "included" in df.columns:
        df = df[df["included"] != 0]
        if df.empty:
            return df
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M").astype(str)
    return df


# Sources that are spend feeds: a POSITIVE amount from one of these is a refund
# (e.g. an Amazon return credit), which should reduce that category's spend
# rather than count as income. A positive from any other source (bank, generic)
# is real money in (payroll, interest, …) and counts as income.
_SPEND_SOURCES = {"credit_card", "amazon"}


def _split(df):
    """Add per-row 'spend' and 'income' columns. A refund (positive on a spend
    feed) contributes NEGATIVE spend, so it nets against same-category purchases;
    it never counts as income. Savings (income - spend) still equals the net of
    all amounts."""
    is_refund = (df["amount"] > 0) & (df["source"].isin(_SPEND_SOURCES))
    df = df.copy()
    df["spend"] = 0.0
    df.loc[df["amount"] < 0, "spend"] = -df["amount"]
    df.loc[is_refund, "spend"] = -df["amount"]          # positive amount -> reduces spend
    df["income"] = 0.0
    df.loc[(df["amount"] > 0) & ~is_refund, "income"] = df["amount"]
    return df


def spending_by_category_over_time(transactions):
    """Return a DataFrame indexed by month, one column per category (spend, positive)."""
    df = _df(transactions)
    if df.empty:
        return pd.DataFrame()
    spend = _split(df)
    spend = spend[spend["spend"] != 0]
    if spend.empty:
        return pd.DataFrame()
    pivot = spend.pivot_table(
        index="month", columns="category", values="spend", aggfunc="sum", fill_value=0
    )
    return pivot.sort_index()


def monthly_savings(transactions):
    """Income, spend, savings, savings_rate per month, plus a `complete` flag.

    A month is `complete` only when our data spans the whole calendar month.
    Statement cycles rarely align to month boundaries, so the first and last
    months present are usually partial — comparing them (or showing a delta
    between two partial months) is misleading, so callers should lean on the
    flag and prefer the latest complete month for headline figures."""
    df = _df(transactions)
    if df.empty:
        return pd.DataFrame()
    s = _split(df).groupby("month")[["income", "spend"]].sum()
    s["savings"] = s["income"] - s["spend"]
    s["savings_rate"] = [
        (sav / inc) if inc > 0 else float("nan")
        for sav, inc in zip(s["savings"], s["income"])
    ]
    dmin, dmax = df["date"].min(), df["date"].max()

    def _complete(m):
        # Compare at day granularity: transactions are date-only (midnight), while
        # Period.end_time is the last nanosecond of the month — so a row dated on
        # the last calendar day still fully covers the month's end.
        p = pd.Period(m, freq="M")
        return bool(dmin.normalize() <= p.start_time.normalize()
                    and dmax.normalize() >= p.end_time.normalize())

    s["complete"] = [_complete(m) for m in s.index]
    return s.sort_index()


def latest_complete_month(savings):
    """Return the label of the most recent fully-covered month, or None."""
    if savings is None or savings.empty or "complete" not in savings.columns:
        return None
    complete = savings[savings["complete"]]
    return complete.index[-1] if not complete.empty else None


def category_totals(transactions):
    """Net spend per category across all time (positive numbers; refunds netted)."""
    df = _df(transactions)
    if df.empty:
        return {}
    spend = _split(df).groupby("category")["spend"].sum()
    spend = spend[spend > 0]
    return spend.sort_values(ascending=False).to_dict()


def income_by_category(transactions):
    """Total income per category across all time (positive numbers)."""
    df = _df(transactions)
    if df.empty:
        return {}
    inc = _split(df).groupby("category")["income"].sum()
    inc = inc[inc > 0]
    if inc.empty:
        return {}
    return inc.sort_values(ascending=False).to_dict()


def spend_by_parent(transactions, parents):
    """Net spend grouped by parent category. Categories with no parent roll up
    under their own name. `parents` is {category_name: parent_name}."""
    out = {}
    for cat, amt in category_totals(transactions).items():
        grp = (parents.get(cat) or "").strip() or cat
        out[grp] = out.get(grp, 0.0) + amt
    return dict(sorted(out.items(), key=lambda kv: kv[1], reverse=True))


def budget_status(transactions, budgets, parents=None, as_of=None):
    """Pro-rated budget tracking for the CURRENT calendar month.

    For each budget (on a leaf category or a parent name) returns spent so far,
    the pace-expected amount for today (`budget * day/days_in_month`), a
    straight-line projection to month end, and a status: 'on_track' (at/under
    pace), 'ahead' (over pace but under cap), or 'over' (past the cap)."""
    import calendar
    parents = parents or {}
    today = as_of or date.today()
    month = today.strftime("%Y-%m")
    days_in_month = calendar.monthrange(today.year, today.month)[1]
    frac = max(today.day, 1) / days_in_month

    df = _df(transactions)
    spend_by_cat = {}
    if not df.empty:
        cur = _split(df[df["month"] == month])
        if not cur.empty:
            spend_by_cat = cur.groupby("category")["spend"].sum().to_dict()
    parent_names = {(v or "").strip() for v in parents.values()} - {""}

    out = []
    for b in budgets:
        cat = b["category"]
        amt = float(b.get("amount") or 0)
        if cat in parent_names:        # a budget on a parent rolls up its children
            spent = sum(v for k, v in spend_by_cat.items()
                        if (parents.get(k) or "").strip() == cat)
        else:
            spent = float(spend_by_cat.get(cat, 0.0))
        expected = amt * frac
        projected = spent / frac if frac > 0 else spent
        if amt > 0 and spent > amt:
            status = "over"
        elif spent > expected:
            status = "ahead"
        else:
            status = "on_track"
        out.append({**b, "spent": round(spent, 2), "budget": amt,
                    "expected_to_date": round(expected, 2),
                    "projected_eom": round(projected, 2),
                    "pct": (spent / amt) if amt else 0.0, "status": status})
    return out


def month_over_month_change(transactions):
    """Per-category % change from the previous month to the latest month."""
    pivot = spending_by_category_over_time(transactions)
    if pivot.empty or len(pivot) < 2:
        return {}
    latest, prev = pivot.iloc[-1], pivot.iloc[-2]
    changes = {}
    for cat in pivot.columns:
        p, l = prev.get(cat, 0), latest.get(cat, 0)
        if p == 0:
            changes[cat] = None if l == 0 else 100.0
        else:
            changes[cat] = (l - p) / p * 100
    return changes


# Description hints that a row is a money-move rather than spend/income.
_TRANSFER_HINTS = ("transfer", "zelle", "venmo", "withdrawal", "deposit", "wire",
                   "online banking", "paypal", "cash app", "payment to",
                   "payment from")


def _looks_transfer(desc):
    d = (desc or "").lower()
    return any(h in d for h in _TRANSFER_HINTS)


def find_transfer_pairs(txns, *, days=3):
    """Detect internal transfers: an outflow matched to an inflow of equal
    magnitude within `days` days — e.g. a Zelle from one partner to the other, or
    a move between your own accounts. Such pairs net to zero and shouldn't count
    as spend or income, so the UI can exclude both sides.

    Greedy nearest-date matching by magnitude; each transaction is used at most
    once. A pair only counts when it looks like a genuine transfer — the two
    sides belong to different people, OR a transfer keyword appears in either
    description — which keeps coincidental same-magnitude purchases out. Pairs
    where both sides are on a spend feed (credit_card/amazon) are skipped, since
    those are a purchase and its refund (already handled by refund-netting).

    Matching is currency-aware: the canonical pivot is USD (`amount_base`).
    Two legs match only when their USD base amounts are equal within a small
    tolerance (0.02 USD). This prevents a ₪370 outflow from pairing with a
    $370 inflow just because the raw numbers happen to be equal. If
    `amount_base` is absent on a row, the raw `amount` is used as a fallback
    so behaviour degrades gracefully on un-enriched data.

    Returns a list (largest amount first) of dicts: amount, out_id, in_id,
    out_date, in_date, out_desc, in_desc, out_person, in_person, days_apart,
    cross_person, both_included, out_currency, in_currency."""
    from collections import defaultdict

    # Tolerance for USD-base comparison (covers floating-point drift; 2 cents).
    _BASE_TOL = 0.02

    def _base_key(t):
        """USD base for bucketing — falls back to raw amount if not enriched."""
        base = t.get("amount_base")
        amt = float(t["amount"])
        if base is not None:
            return float(base)
        return amt

    outs, ins = defaultdict(list), defaultdict(list)
    for t in txns:
        amt = float(t["amount"])
        base = _base_key(t)
        if round(abs(base), 2) == 0:
            continue
        rec = {"t": t, "date": pd.to_datetime(t["date"]), "base": base}
        (outs if amt < 0 else ins)[round(abs(base), 2)].append(rec)

    pairs = []
    for key, olist in outs.items():
        # Collect all inflow buckets whose rounded base is close enough.
        candidate_items = []
        for ikey, ilist in ins.items():
            if abs(ikey - key) <= _BASE_TOL:
                candidate_items.extend((j_offset, rec)
                                       for j_offset, rec in enumerate(ilist))

        if not candidate_items:
            continue

        # Re-sort olist and build indexed access for the matched inflow pool.
        olist.sort(key=lambda r: r["date"])

        # Build an indexed list of all inflow candidates (deduped by their
        # original position within ins).  We track which global indices are used.
        # Simpler: just work with the flat candidate list + a used set on t["id"].
        used_ids = set()
        for o in olist:
            ot = o["t"]
            best = None  # (rec, gap)
            for _, i in candidate_items:
                it = i["t"]
                if it.get("id") in used_ids:
                    continue
                gap = abs((i["date"] - o["date"]).days)
                if gap > days:
                    continue
                if (ot.get("source") in _SPEND_SOURCES
                        and it.get("source") in _SPEND_SOURCES):
                    continue
                cross = ot.get("person_id") != it.get("person_id")
                if not (cross or _looks_transfer(ot.get("description"))
                        or _looks_transfer(it.get("description"))):
                    continue
                if best is None or gap < best[1]:
                    best = (i, gap)
            if best is None:
                continue
            i_rec, gap = best
            it = i_rec["t"]
            used_ids.add(it.get("id"))
            pairs.append({
                "amount": key,
                "out_id": ot.get("id"), "in_id": it.get("id"),
                "out_date": ot["date"], "in_date": it["date"],
                "out_desc": ot.get("description", ""),
                "in_desc": it.get("description", ""),
                "out_person": ot.get("person_id"), "in_person": it.get("person_id"),
                "days_apart": gap,
                "cross_person": ot.get("person_id") != it.get("person_id"),
                "both_included": bool(ot.get("included", 1)) and bool(it.get("included", 1)),
                "out_currency": ot.get("currency", "USD"),
                "in_currency": it.get("currency", "USD"),
                # Original leg amounts in each leg's own currency (for UI display).
                "out_amount": abs(float(ot["amount"])),
                "in_amount": abs(float(it["amount"])),
            })
    pairs.sort(key=lambda p: p["amount"], reverse=True)
    return pairs


def cash_flow(transactions):
    """Per-month cash flow for the cash-flow chart: a DataFrame with columns
    [month, income, spend, net, cumulative]. `net` is income − spend for the
    month; `cumulative` is the running sum of net across months (the savings
    trajectory). Empty input → empty frame."""
    s = monthly_savings(transactions)
    if s.empty:
        return pd.DataFrame()
    out = s[["income", "spend"]].copy()
    out["net"] = out["income"] - out["spend"]
    out["cumulative"] = out["net"].cumsum()
    return out.reset_index()


def spending_alerts(transactions, *, baseline_months=3, threshold_pct=40.0,
                    min_amount=50.0):
    """Flag categories whose spend in the latest *complete* month departs sharply
    from a rolling baseline (the mean of up to `baseline_months` prior complete
    months).

    A category is flagged when the change is both material (≥ `min_amount`) and
    large (≥ `threshold_pct`). A category with no baseline spend that suddenly
    appears is flagged as `new`. Returns a list sorted by absolute dollar change:
    {category, current, baseline, delta, pct, direction ('up'|'down'), new}.
    Partial months are excluded so a half-finished statement cycle doesn't read
    as a spending drop."""
    pivot = spending_by_category_over_time(transactions)
    if pivot.empty:
        return []
    sav = monthly_savings(transactions)
    if not sav.empty and "complete" in sav.columns:
        complete = set(sav.index[sav["complete"]])
        months = [m for m in pivot.index if m in complete]
    else:
        months = list(pivot.index)
    if len(months) < 2:
        return []
    current = months[-1]
    baseline = months[max(0, len(months) - 1 - baseline_months):len(months) - 1]
    if not baseline:
        return []
    cur_row = pivot.loc[current]
    base_df = pivot.loc[baseline]
    alerts = []
    for cat in pivot.columns:
        c = float(cur_row.get(cat, 0.0))
        b = float(base_df[cat].mean()) if cat in base_df.columns else 0.0
        delta = c - b
        if abs(delta) < min_amount:
            continue
        if b == 0:
            if c >= min_amount:
                alerts.append({"category": cat, "current": round(c, 2),
                               "baseline": 0.0, "delta": round(delta, 2),
                               "pct": None, "direction": "up", "new": True})
            continue
        pct = delta / b * 100
        if abs(pct) >= threshold_pct:
            alerts.append({"category": cat, "current": round(c, 2),
                           "baseline": round(b, 2), "delta": round(delta, 2),
                           "pct": round(pct, 1),
                           "direction": "up" if delta > 0 else "down", "new": False})
    alerts.sort(key=lambda a: abs(a["delta"]), reverse=True)
    return alerts


def net_worth(accounts):
    """{'assets', 'liabilities', 'net'} from a list of account dicts.

    balance is a positive magnitude; is_asset (1/0) decides the sign, never the
    balance itself. Empty -> all zeros."""
    assets = sum(a["balance"] for a in accounts if a["is_asset"])
    liabilities = sum(a["balance"] for a in accounts if not a["is_asset"])
    return {"assets": float(assets), "liabilities": float(liabilities),
            "net": float(assets - liabilities)}


def month_end_balances(transactions):
    """For transactions carrying a running `balance`, the balance of the LAST
    transaction in each month — i.e. the month-end balance. Returns a list of
    {month, date, balance} sorted by month. The last transaction is the one with
    the greatest (date, id), since ids increase in statement/file order. Rows
    without a balance are ignored (e.g. credit-card feeds, or pre-upgrade data)."""
    bymonth = {}
    for t in transactions:
        if t.get("balance") is None:
            continue
        m = t["date"][:7]
        key = (t["date"], t.get("id", 0))
        if m not in bymonth or key >= bymonth[m]["_key"]:
            bymonth[m] = {"month": m, "date": t["date"],
                          "balance": float(t["balance"]), "_key": key}
    return [{k: v for k, v in bymonth[m].items() if k != "_key"}
            for m in sorted(bymonth)]


def reconcile(rows, currency=None):
    """Tie out a bank statement against its running-balance column.

    `rows` are transaction dicts carrying 'amount' and (for bank feeds) a running
    'balance'. We sort by date (stable, so same-day rows keep statement order),
    take the opening balance as `first.balance - first.amount`, and check that
    opening + Σ(all amounts) lands on the last row's balance. Σ is order-
    independent, so this is robust to forward- or reverse-chronological exports.

    `currency` is the statement's own currency code (e.g. "USD", "ILS"). When
    supplied it is included verbatim in the returned dict — raw, not converted.

    Returns None when fewer than two rows carry a balance (e.g. a credit-card
    feed has no running balance to reconcile). Otherwise a dict:
    {ok, begin, end, sum_amounts, computed_end, discrepancy, n, chain_breaks}
    plus `currency` when provided."""
    bal = [r for r in rows
           if r.get("balance") is not None and r.get("amount") is not None]
    if len(bal) < 2:
        return None
    bal = sorted(bal, key=lambda r: r["date"])      # stable: keeps intra-day order
    amounts = [float(r["amount"]) for r in bal]
    balances = [float(r["balance"]) for r in bal]
    begin = balances[0] - amounts[0]
    end = balances[-1]
    total = sum(amounts)
    computed_end = begin + total
    discrepancy = round(end - computed_end, 2)
    # Count rows where the running balance doesn't equal the prior balance plus
    # this row's amount — points at where a statement stops tying out.
    chain_breaks = sum(
        1 for i in range(1, len(bal))
        if abs(balances[i] - (balances[i - 1] + amounts[i])) >= 0.01)
    result = {"ok": abs(discrepancy) < 0.01, "begin": round(begin, 2),
              "end": round(end, 2), "sum_amounts": round(total, 2),
              "computed_end": round(computed_end, 2), "discrepancy": discrepancy,
              "n": len(bal), "chain_breaks": chain_breaks}
    if currency is not None:
        result["currency"] = currency
    return result


def net_worth_trend(snapshots):
    """Step-series DataFrame[date, assets, liabilities, net] over every date that
    has a snapshot. Each account contributes its most-recent snapshot on or
    before each date (forward-fill); an account with no snapshot yet contributes
    0. Each snapshot must carry its account's is_asset. Empty -> empty frame."""
    if not snapshots:
        return pd.DataFrame()
    df = pd.DataFrame(snapshots)
    df["date"] = pd.to_datetime(df["date"])
    out = []
    for d in sorted(df["date"].unique()):
        # latest snapshot per account on or before this date
        latest = df[df["date"] <= d].sort_values("date").groupby("account_id").tail(1)
        assets = latest.loc[latest["is_asset"] == 1, "balance"].sum()
        liabilities = latest.loc[latest["is_asset"] == 0, "balance"].sum()
        out.append({"date": pd.Timestamp(d).date().isoformat(),
                    "assets": float(assets), "liabilities": float(liabilities),
                    "net": float(assets - liabilities)})
    return pd.DataFrame(out)


def goal_progress(goals, actual_monthly_savings=None):
    """Attach percent-complete, monthly-needed, pace status, and projected completion.

    Parameters
    ----------
    goals : list of dicts  —  raw goal rows from the DB.
    actual_monthly_savings : float | None
        The household's average monthly savings in USD (base currency).  When
        provided, each goal receives a ``status`` of "ahead" / "on_track" /
        "behind" / "overdue".  When None, ``status`` is None for goals that
        need pace info (no pace info available).

    Returns
    -------
    List of goal dicts with added keys:
        percent               – float, 0-100
        monthly_needed        – float | None  (None when no target_date)
        status                – "ahead" | "on_track" | "behind" | "overdue" | None
        projected_completion  – ISO date str | None

    Decisions / design notes
    ------------------------
    * on_track tolerance band: ±10 % of monthly_needed.  A goal is "on_track"
      when actual savings fall within [0.90 * monthly_needed, 1.10 * monthly_needed].
      This is a narrow but sensible band; callers can document it for users.
    * overdue: months_left == 0 AND remaining > 0.  This fixes the pre-existing
      bug that silently set monthly_needed = remaining instead of flagging it.
    * status is None when: no target_date AND no actual_monthly_savings that
      would let us derive pace.  For goals without a target_date, status is
      also None (we can't compare against a monthly_needed we don't have), but
      projected_completion IS still computed when actual_monthly_savings > 0.
    * projected_completion: ceil(remaining / actual_monthly_savings) months from
      today, as an ISO date (first day of the projected completion month).
      None when savings <= 0, unknown, or goal already complete.
    """
    import math as _math

    ON_TRACK_TOLERANCE = 0.10  # ±10 % of monthly_needed

    out = []
    today = date.today()
    for g in goals:
        target = g["target_amount"] or 0
        saved = g["saved_amount"] or 0
        pct = (saved / target * 100) if target else 0
        remaining = max(target - saved, 0)
        monthly_needed = None
        status = None
        projected_completion = None

        # ── target-date branch ──────────────────────────────────────────────
        if g.get("target_date"):
            try:
                td = pd.to_datetime(g["target_date"]).date()
                months_left = (td.year - today.year) * 12 + (td.month - today.month)

                if months_left <= 0 and remaining > 0:
                    # Overdue: deadline is this month or past and goal is unmet.
                    status = "overdue"
                    # monthly_needed stays None — no forward-looking figure is meaningful.
                else:
                    months_left = max(months_left, 0)
                    if months_left > 0:
                        monthly_needed = remaining / months_left

                    # Pace status (requires actual_monthly_savings)
                    if actual_monthly_savings is not None and monthly_needed is not None and remaining > 0:
                        lo = monthly_needed * (1 - ON_TRACK_TOLERANCE)
                        hi = monthly_needed * (1 + ON_TRACK_TOLERANCE)
                        if actual_monthly_savings < lo:
                            status = "behind"
                        elif actual_monthly_savings > hi:
                            status = "ahead"
                        else:
                            status = "on_track"
            except Exception:
                pass

        # ── projected_completion ─────────────────────────────────────────────
        # Computed whenever actual_monthly_savings > 0 and goal is not yet met.
        if actual_monthly_savings is not None and actual_monthly_savings > 0 and remaining > 0:
            months_needed = _math.ceil(remaining / actual_monthly_savings)
            # Advance today by months_needed calendar months.
            proj_year = today.year + (today.month + months_needed - 1) // 12
            proj_month = (today.month + months_needed - 1) % 12 + 1
            projected_completion = date(proj_year, proj_month, 1).isoformat()

        out.append({
            **g,
            "percent": round(pct, 1),
            "monthly_needed": monthly_needed,
            "status": status,
            "projected_completion": projected_completion,
        })
    return out


# ==========================================================================
# Advanced analytics: temporal filtering, comparison, drill-down, people.
# Keystone: filter_transactions() returns a LIST OF TXN DICTS, so every function
# above works unchanged on any filtered / compared / per-person subset — refund
# netting (_split) and the `included` flag stay correct for free.
# ==========================================================================

DOW_NAMES = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
# Built-in recurring "events" — always available, no DB row needed.
WORKDAYS = {"name": "Workdays", "kind": "recurring", "rule": {"dow": [0, 1, 2, 3, 4]}}
WEEKENDS = {"name": "Weekends", "kind": "recurring", "rule": {"dow": [5, 6]}}


def _rule_of(event):
    """Recurring-rule dict for an event (parses JSON when stored as text)."""
    rule = event.get("rule") if event else None
    if isinstance(rule, str):
        try:
            rule = json.loads(rule)
        except (ValueError, TypeError):
            rule = {}
    return rule or {}


def _day_matches_rule(d, rule):
    """A day matches if it satisfies EVERY clause present (dow / day_of_month /
    month_day 'MM-DD'). d is a date/Timestamp."""
    if "dow" in rule and d.weekday() not in rule["dow"]:
        return False
    if "day_of_month" in rule and d.day not in rule["day_of_month"]:
        return False
    if "month_day" in rule and f"{d.month:02d}-{d.day:02d}" not in rule["month_day"]:
        return False
    return True


def _with_dates(df):
    """Add 'dow' (0=Mon..6=Sun) and 'is_weekend'. df must be a _df() frame."""
    df = df.copy()
    df["dow"] = df["date"].dt.dayofweek
    df["is_weekend"] = df["dow"] >= 5
    return df


def event_mask(df, event):
    """Boolean Series selecting df rows belonging to `event`.

    Kinds: 'window' (a date range), 'recurring' (a day rule), or 'tagged' (no
    date predicate of its own). For ANY kind, transactions explicitly tagged to
    the event via `event['ids']` are also included (union) — so a window event
    can pick up a straggler dated just outside it."""
    kind = event.get("kind")
    if kind == "window":
        start = pd.to_datetime(event.get("start_date"))
        end = pd.to_datetime(event.get("end_date"))
        mask = (df["date"] >= start) & (df["date"] <= end)
    elif kind == "tagged":
        mask = pd.Series(False, index=df.index)
    else:
        rule = _rule_of(event)
        mask = df["date"].apply(lambda d: _day_matches_rule(d, rule))
    ids = event.get("ids")
    if ids and "id" in df.columns:
        mask = mask | df["id"].isin(set(ids))
    return mask


def filter_transactions(txns, *, day_types=None, dow=None, date_range=None,
                        event=None, categories=None, people=None, months=None):
    """Return a FILTERED LIST OF TXN DICTS. All conditions AND together; None means
    no constraint. The result feeds back into every other analytics function, so
    refund-netting and `included` are preserved automatically.

    months: iterable of 'YYYY-MM' strings to include (e.g. pick specific,
    possibly non-contiguous months); None = all months."""
    df = _df(txns)
    if df.empty:
        return []
    df = _with_dates(df)
    mask = pd.Series(True, index=df.index)
    if months:
        mask &= df["month"].isin(list(months))
    if day_types:
        want_wknd, want_wkdy = "weekend" in day_types, "weekday" in day_types
        if want_wknd and not want_wkdy:
            mask &= df["is_weekend"]
        elif want_wkdy and not want_wknd:
            mask &= ~df["is_weekend"]
    if dow is not None:
        mask &= df["dow"].isin(list(dow))
    if date_range:
        s, e = date_range
        if s:
            mask &= df["date"] >= pd.to_datetime(s)
        if e:
            mask &= df["date"] <= pd.to_datetime(e)
    if event:
        mask &= event_mask(df, event)
    if categories is not None:
        mask &= df["category"].isin(list(categories))
    if people is not None and "person_id" in df.columns:
        mask &= df["person_id"].isin(list(people))
    keep = set(df.index[mask])
    return [t for i, t in enumerate(txns) if i in keep]


def count_matching_days(date_min, date_max, *, day_types=None, dow=None, event=None):
    """Calendar days in [date_min, date_max] satisfying the predicate — the fair
    divisor for per-day normalization."""
    d0 = pd.to_datetime(date_min).date()
    d1 = pd.to_datetime(date_max).date()
    if d1 < d0:
        return 0
    if event and event.get("kind") == "window":
        s = max(d0, pd.to_datetime(event["start_date"]).date())
        e = min(d1, pd.to_datetime(event["end_date"]).date())
        return max((e - s).days + 1, 0)
    dows = None
    if dow is not None:
        dows = set(dow)
    elif day_types:
        dows = set()
        if "weekday" in day_types:
            dows |= {0, 1, 2, 3, 4}
        if "weekend" in day_types:
            dows |= {5, 6}
    rule = _rule_of(event) if event else None
    n, cur = 0, d0
    while cur <= d1:
        ok = True
        if dows is not None and cur.weekday() not in dows:
            ok = False
        if rule and not _day_matches_rule(cur, rule):
            ok = False
        n += 1 if ok else 0
        cur += timedelta(days=1)
    return n


def per_day_normalize(txns, start, end):
    """Totals over the subset, divided by the inclusive calendar-day count of
    [start, end]. Makes unequal-length windows comparable."""
    days = max((pd.to_datetime(end).date() - pd.to_datetime(start).date()).days + 1, 1)
    df = _df(txns)
    if df.empty:
        return {"spend": 0.0, "income": 0.0, "savings": 0.0, "days": days,
                "spend_per_day": 0.0, "income_per_day": 0.0, "savings_per_day": 0.0}
    s = _split(df)
    spend, income = float(s["spend"].sum()), float(s["income"].sum())
    sav = income - spend
    return {"spend": spend, "income": income, "savings": sav, "days": days,
            "spend_per_day": spend / days, "income_per_day": income / days,
            "savings_per_day": sav / days}


def _bucket_days(txns, kw):
    """Number of days the bucket `kw` (filter kwargs) covers, for per-day fairness."""
    rng = kw.get("date_range")
    if rng and rng[0] and rng[1]:
        return max((pd.to_datetime(rng[1]).date()
                    - pd.to_datetime(rng[0]).date()).days + 1, 1)
    df = _df(txns)
    if df.empty:
        return 1
    dmin, dmax = df["date"].min().date(), df["date"].max().date()
    return count_matching_days(dmin, dmax, day_types=kw.get("day_types"),
                               dow=kw.get("dow"), event=kw.get("event")) or 1


def compare(txns, group_a, group_b, *, metric="spend"):
    """Compare two buckets. group_a/group_b are dicts of filter_transactions
    kwargs (plus an optional 'label'). Returns a tidy DataFrame
    [bucket, category, total, n_days, per_day, share]."""
    def build(group):
        label = group.get("label")
        kw = {k: v for k, v in group.items() if k != "label"}
        sub = filter_transactions(txns, **kw)
        totals = category_totals(sub) if metric == "spend" else income_by_category(sub)
        n_days = _bucket_days(txns, kw)
        grand = sum(totals.values()) or 0.0
        return [{"bucket": label or "?", "category": c, "total": amt,
                 "n_days": n_days, "per_day": amt / n_days,
                 "share": (amt / grand if grand else 0.0)}
                for c, amt in totals.items()]
    return pd.DataFrame(build(group_a) + build(group_b))


def vendor_of(description, vendor_rules=None):
    """Canonical vendor for a description. The first vendor rule whose keyword is a
    substring wins (e.g. 'amazon'/'amzn' -> 'Amazon', collapsing Amazon.com,
    AMAZON MKTPL, AMAZON PRIME into one). With no matching rule, fall back to the
    auto merchant key (keyword_from_desc) so the drill-down still works unconfigured.
    vendor_rules: list of (name, [keywords])."""
    text = (description or "").lower()
    for name, kws in (vendor_rules or []):
        for kw in kws:
            kw = (kw or "").strip().lower()
            if kw and kw in text:
                return name
    return keyword_from_desc(description)


def drill(txns, level, *, parent=None, vendor_rules=None):
    """One hierarchy level:
    'category'           -> {category: net spend}            (== category_totals)
    'vendor', parent=C   -> {vendor: net spend} within category C, grouped by
                            vendor_of (rules collapse merchant variants)
    'rows',   parent=V   -> txn dicts whose vendor_of == V (pass a category-scoped
                            txns list so vendors from other categories don't mix).
    Level 'merchant' is accepted as an alias of 'vendor' for back-compat."""
    if level == "category":
        return category_totals(txns)
    if level in ("vendor", "merchant"):
        sub = [t for t in txns if t.get("category") == parent]
        df = _df(sub)
        if df.empty:
            return {}
        s = _split(df).copy()
        s["vendor"] = [vendor_of(d, vendor_rules) for d in s["description"]]
        m = s.groupby("vendor")["spend"].sum()
        m = m[m > 0]
        return m.sort_values(ascending=False).to_dict()
    if level == "rows":
        return [t for t in txns
                if vendor_of(t.get("description", ""), vendor_rules) == parent]
    return {}


# ==========================================================================
# Recurring / subscription detection. Pure, no DB: re-run each render over the
# transaction list. Groups merchants via vendor_of (so AMAZON MKTPL collapses to
# Amazon), routes through _df/_split (excluded rows + refund-netting honoured),
# and a vendor that nets to ~zero is not treated as a live subscription.
# ==========================================================================

# Nominal length of each cadence, in days. ~30.44 / ~91.31 / ~365.25 keep the
# month/quarter/year averages honest (leap years, uneven months).
_CADENCE_DAYS = {"weekly": 7.0, "monthly": 30.44, "quarterly": 91.31, "yearly": 365.25}


def _snap_cadence(median_gap):
    """Nearest cadence (name, period_days) whose nominal length is within ±25% of
    `median_gap`, or None if the gap matches no known cadence. Picks the closest
    when several qualify."""
    best = None
    for name, period in _CADENCE_DAYS.items():
        err = abs(median_gap - period)
        if err <= 0.25 * period and (best is None or err < best[2]):
            best = (name, period, err)
    return (best[0], best[1]) if best else None


def recurring_charges(txns, vendor_rules=None):
    """Detect recurring charges (subscriptions, regular bills) from a txn list.

    Groups spend by vendor (vendor_of), aggregates to one charge per day (a
    subscription bills once per cycle), and flags a vendor as recurring when it
    has >=3 charges whose median gap snaps to a known cadence (weekly/monthly/
    quarterly/yearly) and whose gaps are reasonably regular. Each match is
    classified 'fixed' (amount barely varies) or 'variable' (regular cadence,
    varying amount — usage-based bills like phone/electric). Returns a list of
    dicts sorted by (confidence, monthly_cost) descending."""
    df = _df(txns)
    if df.empty:
        return []
    s = _split(df)
    s = s[s["spend"] > 0].copy()
    if s.empty:
        return []
    s["vendor"] = [vendor_of(d, vendor_rules) for d in s["description"]]

    out = []
    for vendor, grp in s.groupby("vendor"):
        # One charge per calendar day: a real subscription bills once per cycle,
        # and same-day duplicates (e.g. a busy merchant) would fake a 0-day gap.
        byday = grp.groupby(grp["date"].dt.normalize())["spend"].sum().sort_index()
        if len(byday) < 3:
            continue
        dates = list(byday.index)
        amounts = [float(a) for a in byday.values]
        gaps = [(dates[i] - dates[i - 1]).days for i in range(1, len(dates))]
        median_gap = statistics.median(gaps)
        if median_gap <= 0:
            continue
        snapped = _snap_cadence(median_gap)
        if not snapped:
            continue
        cadence, period = snapped
        gap_mean = statistics.fmean(gaps)
        gap_cv = (statistics.pstdev(gaps) / gap_mean) if gap_mean else 0.0
        if gap_cv > 0.4:           # gaps too irregular to call it recurring
            continue

        typical = statistics.median(amounts)
        amt_mean = statistics.fmean(amounts)
        amt_cv = (statistics.pstdev(amounts) / amt_mean) if amt_mean else 0.0
        kind = "fixed" if amt_cv <= 0.10 else "variable"

        # Prior amounts (all but the last) let the anomaly pass spot a price
        # change even though that change itself bumps the overall amount CV into
        # 'variable' territory.
        prior = amounts[:-1]
        prior_typical = statistics.median(prior)
        prior_mean = statistics.fmean(prior)
        prior_cv = (statistics.pstdev(prior) / prior_mean) if prior_mean else 0.0

        confidence = max(0.0, min(1.0, statistics.fmean([
            1 - min(gap_cv, 1.0),             # regular timing
            min(len(byday) / 6.0, 1.0),       # more occurrences -> surer
            1 - min(amt_cv, 1.0),             # steady amount
        ])))
        monthly_cost = typical * (_CADENCE_DAYS["monthly"] / period)
        mode = grp["category"].mode()
        category = mode.iloc[0] if not mode.empty else None
        out.append({
            "vendor": vendor,
            "category": category,
            "cadence": cadence,
            "kind": kind,
            "typical_amount": round(typical, 2),
            "prior_typical": round(prior_typical, 2),
            "prior_stable": bool(prior_cv <= 0.10),
            "first_date": dates[0].date().isoformat(),
            "last_date": dates[-1].date().isoformat(),
            "last_amount": round(amounts[-1], 2),
            "next_expected": (dates[-1] + timedelta(days=round(median_gap))).date().isoformat(),
            "count": len(byday),
            "monthly_cost": round(monthly_cost, 2),
            "annual_cost": round(monthly_cost * 12, 2),
            "confidence": round(confidence, 3),
        })
    out.sort(key=lambda r: (r["confidence"], r["monthly_cost"]), reverse=True)
    return out


def bills_due_this_month(recurring, as_of=None):
    """Recurring charges whose NEXT expected date falls between today and the end
    of the current calendar month — the bills still to hit before month-end.
    Returns {count, amount}, amount summing each due charge's typical amount.
    Bounds are inclusive of both today and the last day of the month."""
    import calendar
    today = pd.to_datetime(as_of).date() if as_of else date.today()
    last_day = calendar.monthrange(today.year, today.month)[1]
    month_end = date(today.year, today.month, last_day)
    due = [
        r for r in recurring
        if r.get("next_expected") and today <= date.fromisoformat(r["next_expected"]) <= month_end
    ]
    amount = sum(r.get("typical_amount", 0.0) for r in due)
    return {"count": len(due), "amount": round(amount, 2)}


def committed_monthly(recurring):
    """Total recurring monthly spend, split into 'fixed' / 'variable' / 'total'."""
    fixed = sum(r["monthly_cost"] for r in recurring if r["kind"] == "fixed")
    variable = sum(r["monthly_cost"] for r in recurring if r["kind"] == "variable")
    return {"fixed": round(fixed, 2), "variable": round(variable, 2),
            "total": round(fixed + variable, 2)}


def recurring_anomalies(recurring, as_of=None):
    """Flags derived from each match's own history (no persistence):
    'price_change' (latest charge departs >15% from a previously-stable price),
    'possibly_canceled' (next_expected is >1.5x the cadence overdue), and 'new'
    (first charge within ~2 cadence periods of `as_of`). Sorted by severity."""
    today = pd.to_datetime(as_of).date() if as_of else date.today()
    out = []
    for r in recurring:
        period = _CADENCE_DAYS[r["cadence"]]
        if r.get("prior_stable") and r["prior_typical"] > 0:
            pct = (r["last_amount"] - r["prior_typical"]) / r["prior_typical"] * 100
            if abs(pct) > 15:
                out.append({"vendor": r["vendor"], "type": "price_change",
                            "detail": f"{r['prior_typical']:.2f} -> {r['last_amount']:.2f}",
                            "pct": round(pct, 1)})
        overdue = (today - date.fromisoformat(r["next_expected"])).days
        if overdue > 1.5 * period:
            out.append({"vendor": r["vendor"], "type": "possibly_canceled",
                        "detail": f"expected ~{r['next_expected']}, nothing since {r['last_date']}",
                        "overdue_days": overdue})
        age = (today - date.fromisoformat(r["first_date"])).days
        # >=3 charges already span ~2 periods, so allow a little headroom.
        if age <= 2.5 * period:
            out.append({"vendor": r["vendor"], "type": "new",
                        "detail": f"first charge {r['first_date']}", "age_days": age})
    order = {"price_change": 0, "possibly_canceled": 1, "new": 2}
    out.sort(key=lambda a: order.get(a["type"], 9))
    return out


def user_overlap(txns, person_a, person_b):
    """Per-category spend for two people. Returns dicts sorted by combined spend:
    {category, a_spend, b_spend, shared, diff(a-b), combined}. `shared` marks
    categories where both spent — the 'mutual spending'."""
    a = category_totals([t for t in txns if t.get("person_id") == person_a])
    b = category_totals([t for t in txns if t.get("person_id") == person_b])
    out = []
    for c in set(a) | set(b):
        av, bv = a.get(c, 0.0), b.get(c, 0.0)
        out.append({"category": c, "a_spend": av, "b_spend": bv,
                    "shared": av > 0 and bv > 0, "diff": av - bv,
                    "combined": av + bv})
    out.sort(key=lambda r: r["combined"], reverse=True)
    return out
