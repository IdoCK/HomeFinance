"""Compute the numbers the dashboard charts and the AI insights both rely on."""

from collections import defaultdict
from datetime import date
import pandas as pd


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
