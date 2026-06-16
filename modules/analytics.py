"""Compute the numbers the dashboard charts and the AI insights both rely on."""

from collections import defaultdict
from datetime import date
import pandas as pd


def _df(transactions):
    df = pd.DataFrame(transactions)
    if df.empty:
        return df
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M").astype(str)
    return df


def spending_by_category_over_time(transactions):
    """Return a DataFrame indexed by month, one column per category (spend, positive)."""
    df = _df(transactions)
    if df.empty:
        return pd.DataFrame()
    spend = df[df["amount"] < 0].copy()
    spend["spend"] = -spend["amount"]
    pivot = spend.pivot_table(
        index="month", columns="category", values="spend", aggfunc="sum", fill_value=0
    )
    return pivot.sort_index()


def monthly_savings(transactions):
    """income - spend per month. Returns DataFrame with income, spend, savings."""
    df = _df(transactions)
    if df.empty:
        return pd.DataFrame()
    g = df.groupby("month")["amount"]
    income = g.apply(lambda s: s[s > 0].sum())
    spend = g.apply(lambda s: -s[s < 0].sum())
    out = pd.DataFrame({"income": income, "spend": spend})
    out["savings"] = out["income"] - out["spend"]
    return out.sort_index()


def category_totals(transactions):
    """Total spend per category across all time (positive numbers)."""
    df = _df(transactions)
    if df.empty:
        return {}
    spend = df[df["amount"] < 0]
    return (-spend.groupby("category")["amount"].sum()).sort_values(ascending=False).to_dict()


def income_by_category(transactions):
    """Total income per category across all time (positive numbers)."""
    df = _df(transactions)
    if df.empty:
        return {}
    inc = df[df["amount"] > 0]
    if inc.empty:
        return {}
    return inc.groupby("category")["amount"].sum().sort_values(ascending=False).to_dict()


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
