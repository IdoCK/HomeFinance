"""Engine tests for net-worth growth metrics: trailing-12m, CAGR, FIRE.

TDD — written BEFORE the implementation, expected to FAIL initially.
"""
import math

from modules import analytics


def _pt(date, net):
    return {"date": date, "assets": net, "liabilities": 0.0, "net": float(net)}


# ---------------------------------------------------------------------------
# net_worth_growth: trailing-12-month change + CAGR
# ---------------------------------------------------------------------------

def test_growth_none_with_too_few_points():
    assert analytics.net_worth_growth([]) is None
    assert analytics.net_worth_growth([_pt("2026-01-01", 1000)]) is None


def test_trailing_12m_uses_snapshot_a_year_back():
    trend = [
        _pt("2025-06-01", 100000),
        _pt("2025-12-01", 110000),
        _pt("2026-06-01", 130000),
    ]
    g = analytics.net_worth_growth(trend)
    # Trailing 12m compares the latest (130k) to the snapshot on/before a year
    # earlier (2025-06-01 = 100k) -> +30k, +30%.
    assert g["trailing_abs"] == 30000.0
    assert round(g["trailing_pct"], 1) == 30.0


def test_trailing_none_when_history_under_a_year():
    trend = [_pt("2026-01-01", 100000), _pt("2026-06-01", 120000)]
    g = analytics.net_worth_growth(trend)
    # No snapshot is a full year old, so a true trailing-12m figure is unknowable.
    assert g["trailing_abs"] is None
    assert g["trailing_pct"] is None


def test_cagr_over_full_span():
    # 100k -> 200k over exactly ~2 years -> CAGR ≈ sqrt(2)-1 ≈ 0.4142.
    trend = [_pt("2024-06-01", 100000), _pt("2026-06-01", 200000)]
    g = analytics.net_worth_growth(trend)
    assert g["cagr"] is not None
    assert math.isclose(g["cagr"], 2 ** 0.5 - 1, abs_tol=0.01)


def test_cagr_none_when_start_not_positive():
    trend = [_pt("2024-06-01", 0), _pt("2026-06-01", 50000)]
    g = analytics.net_worth_growth(trend)
    assert g["cagr"] is None


def test_growth_sorts_unordered_input():
    trend = [_pt("2026-06-01", 130000), _pt("2025-06-01", 100000)]
    g = analytics.net_worth_growth(trend)
    assert g["trailing_abs"] == 30000.0


# ---------------------------------------------------------------------------
# fire_metrics: 25x target + runway
# ---------------------------------------------------------------------------

def test_fire_number_is_25x_annual_expenses():
    m = analytics.fire_metrics(net_worth=250000, annual_expenses=40000, monthly_burn=3000)
    assert m["fire_number"] == 1000000.0
    # 250k of a 1M target = 25%.
    assert round(m["pct_to_fire"], 4) == 0.25


def test_runway_is_net_worth_over_monthly_burn():
    m = analytics.fire_metrics(net_worth=30000, annual_expenses=40000, monthly_burn=3000)
    assert m["runway_months"] == 10.0


def test_fire_handles_zero_expenses_and_burn():
    m = analytics.fire_metrics(net_worth=30000, annual_expenses=0, monthly_burn=0)
    assert m["fire_number"] is None
    assert m["pct_to_fire"] is None
    assert m["runway_months"] is None
