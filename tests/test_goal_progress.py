"""Tests for goal_progress() engine: overdue fix, pace status, projected_completion.

TDD — these are written BEFORE the implementation and are expected to FAIL initially.
"""
import math
from datetime import date, timedelta
import calendar

import pytest

from modules.analytics import goal_progress


def _months_from_today(n: int) -> str:
    """Return an ISO date string n months from today (same day-of-month, clamped to month-end)."""
    today = date.today()
    year = today.year + (today.month + n - 1) // 12
    month = (today.month + n - 1) % 12 + 1
    day = min(today.day, calendar.monthrange(year, month)[1])
    return date(year, month, day).isoformat()


def _this_month() -> str:
    """ISO date in the current month (today)."""
    return date.today().isoformat()


def _last_month() -> str:
    """ISO date one month in the past."""
    return _months_from_today(-1)


# ---------------------------------------------------------------------------
# Helper: make a minimal goal dict
# ---------------------------------------------------------------------------
def _goal(target=10000, saved=2000, target_date=None, horizon="short"):
    return {
        "id": 1,
        "person_id": 1,
        "name": "Test Goal",
        "target_amount": target,
        "saved_amount": saved,
        "target_date": target_date,
        "horizon": horizon,
        "notes": "",
    }


# ===========================================================================
# (a) Overdue: months_left == 0 and goal unmet → status = "overdue"
# ===========================================================================

class TestOverdue:
    def test_past_target_date_unmet_returns_overdue(self):
        """Deadline in the past month with remaining balance → overdue."""
        g = _goal(target=10000, saved=2000, target_date=_last_month())
        result = goal_progress([g])[0]
        assert result["status"] == "overdue"

    def test_current_month_target_date_unmet_returns_overdue(self):
        """Deadline THIS month (months_left == 0) and unmet → overdue."""
        g = _goal(target=10000, saved=2000, target_date=_this_month())
        result = goal_progress([g])[0]
        assert result["status"] == "overdue"

    def test_overdue_not_silently_remaining(self):
        """Regression: the old bug set monthly_needed = remaining. Now status is flagged."""
        g = _goal(target=10000, saved=2000, target_date=_last_month())
        result = goal_progress([g])[0]
        # status must be "overdue" (not None or something else)
        assert result["status"] == "overdue"
        # monthly_needed is still allowed to carry the remaining value, but status must be set
        # (original bug: status didn't exist at all, monthly_needed was silently remaining)

    def test_completed_goal_past_date_not_overdue(self):
        """If target_date is past but goal is already met, not overdue."""
        g = _goal(target=5000, saved=5000, target_date=_last_month())
        result = goal_progress([g])[0]
        # Goal is met, so should not be "overdue"
        assert result["status"] != "overdue"

    def test_no_target_date_no_status(self):
        """No target_date → no pace info → status is None."""
        g = _goal(target=10000, saved=2000, target_date=None)
        result = goal_progress([g])[0]
        assert result["status"] is None

    def test_no_actual_savings_no_pace_status(self):
        """With a future target_date but no actual_monthly_savings passed, status is None."""
        g = _goal(target=10000, saved=2000, target_date=_months_from_today(6))
        result = goal_progress([g])[0]  # no actual_monthly_savings arg
        assert result["status"] is None


# ===========================================================================
# (b) Pace status: behind / ahead / on_track
# ===========================================================================

class TestPaceStatus:
    def test_below_monthly_needed_is_behind(self):
        """Saving $500/mo when $1000/mo is needed → behind."""
        # target=12000, saved=0, 12 months left → needs $1000/mo
        target_date = _months_from_today(12)
        g = _goal(target=12000, saved=0, target_date=target_date)
        result = goal_progress([g], actual_monthly_savings=500)[0]
        assert result["status"] == "behind"

    def test_above_monthly_needed_is_ahead(self):
        """Saving $2000/mo when $1000/mo is needed → ahead."""
        target_date = _months_from_today(12)
        g = _goal(target=12000, saved=0, target_date=target_date)
        result = goal_progress([g], actual_monthly_savings=2000)[0]
        assert result["status"] == "ahead"

    def test_near_monthly_needed_is_on_track(self):
        """Saving within ~10% of needed → on_track."""
        # needs $1000/mo, saving $1050 → 5% above → on_track
        target_date = _months_from_today(12)
        g = _goal(target=12000, saved=0, target_date=target_date)
        result = goal_progress([g], actual_monthly_savings=1050)[0]
        assert result["status"] == "on_track"

    def test_on_track_lower_bound(self):
        """Saving within 10% BELOW needed → still on_track."""
        # needs $1000/mo, saving $950 → 5% below → on_track
        target_date = _months_from_today(12)
        g = _goal(target=12000, saved=0, target_date=target_date)
        result = goal_progress([g], actual_monthly_savings=950)[0]
        assert result["status"] == "on_track"

    def test_just_outside_on_track_below(self):
        """Saving 15% below → behind (outside tolerance)."""
        # needs $1000/mo, saving $850 → 15% below → behind
        target_date = _months_from_today(12)
        g = _goal(target=12000, saved=0, target_date=target_date)
        result = goal_progress([g], actual_monthly_savings=850)[0]
        assert result["status"] == "behind"

    def test_goal_already_complete_no_status(self):
        """Goal already met → status indicates not overdue, projected_completion is None."""
        g = _goal(target=5000, saved=5000, target_date=_months_from_today(6))
        result = goal_progress([g], actual_monthly_savings=1000)[0]
        # Already complete: no pace status needed, projected_completion is None
        assert result["projected_completion"] is None

    def test_overdue_takes_priority_over_pace(self):
        """Overdue status is returned even when actual_monthly_savings is provided."""
        g = _goal(target=10000, saved=2000, target_date=_last_month())
        result = goal_progress([g], actual_monthly_savings=1000)[0]
        assert result["status"] == "overdue"


# ===========================================================================
# (c) projected_completion
# ===========================================================================

class TestProjectedCompletion:
    def test_projected_completion_basic(self):
        """remaining=8000, saving 1000/mo → ~8 months from now."""
        g = _goal(target=10000, saved=2000, target_date=_months_from_today(12))
        result = goal_progress([g], actual_monthly_savings=1000)[0]
        pc = result["projected_completion"]
        assert pc is not None
        # Should be approximately 8 months from today (ceil(8000/1000)=8)
        today = date.today()
        pc_date = date.fromisoformat(pc)
        months_away = (pc_date.year - today.year) * 12 + (pc_date.month - today.month)
        assert months_away == 8

    def test_projected_completion_rounds_up(self):
        """remaining=8500, saving 1000/mo → ceil(8.5)=9 months from now."""
        g = _goal(target=10000, saved=1500, target_date=_months_from_today(12))
        result = goal_progress([g], actual_monthly_savings=1000)[0]
        pc = result["projected_completion"]
        assert pc is not None
        today = date.today()
        pc_date = date.fromisoformat(pc)
        months_away = (pc_date.year - today.year) * 12 + (pc_date.month - today.month)
        assert months_away == 9

    def test_projected_completion_none_when_savings_zero(self):
        """No savings → can't project."""
        g = _goal(target=10000, saved=2000, target_date=_months_from_today(12))
        result = goal_progress([g], actual_monthly_savings=0)[0]
        assert result["projected_completion"] is None

    def test_projected_completion_none_when_savings_negative(self):
        """Negative savings (spending more than earning) → can't project."""
        g = _goal(target=10000, saved=2000, target_date=_months_from_today(12))
        result = goal_progress([g], actual_monthly_savings=-100)[0]
        assert result["projected_completion"] is None

    def test_projected_completion_none_when_no_target_date(self):
        """No target_date → projected_completion still works (uses savings alone)."""
        g = _goal(target=10000, saved=2000, target_date=None)
        result = goal_progress([g], actual_monthly_savings=1000)[0]
        pc = result["projected_completion"]
        # remaining=8000, 8 months from now
        assert pc is not None
        today = date.today()
        pc_date = date.fromisoformat(pc)
        months_away = (pc_date.year - today.year) * 12 + (pc_date.month - today.month)
        assert months_away == 8

    def test_projected_completion_is_iso_string(self):
        """projected_completion must be an ISO date string when set."""
        g = _goal(target=10000, saved=2000, target_date=_months_from_today(12))
        result = goal_progress([g], actual_monthly_savings=1000)[0]
        pc = result["projected_completion"]
        assert pc is not None
        # Must parse as ISO date without exception
        date.fromisoformat(pc)

    def test_projected_completion_none_when_no_actual_savings(self):
        """actual_monthly_savings not provided → projected_completion is None."""
        g = _goal(target=10000, saved=2000, target_date=_months_from_today(12))
        result = goal_progress([g])[0]
        assert result["projected_completion"] is None

    def test_projected_completion_none_when_already_complete(self):
        """Already met → projected_completion is None."""
        g = _goal(target=5000, saved=5000, target_date=_months_from_today(6))
        result = goal_progress([g], actual_monthly_savings=1000)[0]
        assert result["projected_completion"] is None


# ===========================================================================
# (d) Long-horizon goals use future-value annuity math, not flat division.
# ===========================================================================

class TestLongHorizonCompounding:
    def test_long_horizon_needs_less_than_flat_division(self):
        """A long goal earns returns while you save, so the required monthly
        contribution is below remaining / months_left."""
        # target=120k, saved=0, 120 months out → flat would be $1000/mo.
        g = _goal(target=120000, saved=0, target_date=_months_from_today(120), horizon="long")
        result = goal_progress([g])[0]
        assert result["monthly_needed"] is not None
        assert 0 < result["monthly_needed"] < 1000

    def test_long_horizon_matches_annuity_closed_form(self):
        """monthly_needed solves target = saved·(1+r)^n + PMT·((1+r)^n−1)/r."""
        target, saved, n, annual = 120000, 0.0, 120, 0.07
        r = (1 + annual) ** (1 / 12) - 1
        growth = (1 + r) ** n
        expected = (target - saved * growth) * r / (growth - 1)
        g = _goal(target=target, saved=saved, target_date=_months_from_today(n), horizon="long")
        result = goal_progress([g], assumed_annual_return=annual)[0]
        assert math.isclose(result["monthly_needed"], expected, rel_tol=1e-6)

    def test_zero_assumed_return_falls_back_to_flat(self):
        """With a 0% assumed return the annuity collapses to flat division."""
        g = _goal(target=12000, saved=0, target_date=_months_from_today(12), horizon="long")
        result = goal_progress([g], assumed_annual_return=0.0)[0]
        assert math.isclose(result["monthly_needed"], 1000.0, rel_tol=1e-9)

    def test_short_horizon_unaffected_by_compounding(self):
        """Short goals keep flat division — no return assumption applied."""
        g = _goal(target=12000, saved=0, target_date=_months_from_today(12), horizon="short")
        result = goal_progress([g], assumed_annual_return=0.07)[0]
        assert math.isclose(result["monthly_needed"], 1000.0, rel_tol=1e-9)

    def test_long_horizon_clamps_to_zero_when_returns_alone_suffice(self):
        """If existing savings will compound past the target on their own, no
        further contribution is required (monthly_needed clamped to 0)."""
        g = _goal(target=10000, saved=9000, target_date=_months_from_today(120), horizon="long")
        result = goal_progress([g], assumed_annual_return=0.07)[0]
        assert result["monthly_needed"] == 0.0
