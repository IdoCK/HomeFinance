from modules import analytics


def test_projection_linear_ignores_returns():
    pts = analytics.net_worth_projection(10000, 500, 0.0, months=12)
    assert len(pts) == 12
    # No returns -> compounding equals linear, and month 12 = 10000 + 500*12.
    assert pts[-1]["linear"] == 16000.0
    assert pts[-1]["compounding"] == 16000.0


def test_projection_compounding_beats_linear_with_positive_return():
    pts = analytics.net_worth_projection(10000, 500, 0.07, months=120)
    last = pts[-1]
    # Same contributions, but growth makes the compounding curve finish higher.
    assert last["compounding"] > last["linear"]
    # Linear is purely principal + contributions.
    assert last["linear"] == 10000 + 500 * 120


def test_projection_zero_months_is_empty():
    assert analytics.net_worth_projection(10000, 500, 0.07, months=0) == []
