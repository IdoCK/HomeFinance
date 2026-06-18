"""Compute the numbers the dashboard charts and the AI insights both rely on."""

import json
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


def reconcile(rows):
    """Tie out a bank statement against its running-balance column.

    `rows` are transaction dicts carrying 'amount' and (for bank feeds) a running
    'balance'. We sort by date (stable, so same-day rows keep statement order),
    take the opening balance as `first.balance - first.amount`, and check that
    opening + Σ(all amounts) lands on the last row's balance. Σ is order-
    independent, so this is robust to forward- or reverse-chronological exports.

    Returns None when fewer than two rows carry a balance (e.g. a credit-card
    feed has no running balance to reconcile). Otherwise a dict:
    {ok, begin, end, sum_amounts, computed_end, discrepancy, n, chain_breaks}."""
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
    return {"ok": abs(discrepancy) < 0.01, "begin": round(begin, 2),
            "end": round(end, 2), "sum_amounts": round(total, 2),
            "computed_end": round(computed_end, 2), "discrepancy": discrepancy,
            "n": len(bal), "chain_breaks": chain_breaks}


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


def goal_progress(goals):
    """Attach percent-complete and a simple monthly-needed estimate to each goal."""
    out = []
    today = date.today()
    for g in goals:
        target = g["target_amount"] or 0
        saved = g["saved_amount"] or 0
        pct = (saved / target * 100) if target else 0
        monthly_needed = None
        if g.get("target_date"):
            try:
                td = pd.to_datetime(g["target_date"]).date()
                months_left = max(
                    (td.year - today.year) * 12 + (td.month - today.month), 0
                )
                remaining = max(target - saved, 0)
                monthly_needed = remaining / months_left if months_left else remaining
            except Exception:
                pass
        out.append({**g, "percent": round(pct, 1), "monthly_needed": monthly_needed})
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
    """Boolean Series selecting df rows belonging to `event` (window or recurring)."""
    if event.get("kind") == "window":
        start = pd.to_datetime(event.get("start_date"))
        end = pd.to_datetime(event.get("end_date"))
        return (df["date"] >= start) & (df["date"] <= end)
    rule = _rule_of(event)
    return df["date"].apply(lambda d: _day_matches_rule(d, rule))


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
