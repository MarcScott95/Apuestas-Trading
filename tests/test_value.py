import pytest

from apuestas.value import Market, devig, find_value


def test_devig_removes_margin_and_sums_to_one():
    for method in ("multiplicative", "additive", "power"):
        fair = devig([1.91, 1.91], method)
        assert sum(fair) == pytest.approx(1.0)
        assert fair[0] == pytest.approx(0.5, abs=1e-6)


def test_devig_on_a_fair_market_is_a_noop():
    assert devig([2.0, 2.0]) == pytest.approx([0.5, 0.5])


def test_devig_preserves_ordering():
    fair = devig([1.50, 3.00, 6.00])
    assert sum(fair) == pytest.approx(1.0)
    assert fair[0] > fair[1] > fair[2]


def test_devig_methods_disagree_on_lopsided_markets():
    """The choice of method is an assumption, not a detail: on skewed markets
    the methods differ by more than a typical edge."""
    mult = devig([1.10, 8.00], "multiplicative")
    power = devig([1.10, 8.00], "power")
    assert abs(mult[0] - power[0]) > 0.005


def test_devig_rejects_single_outcome():
    with pytest.raises(ValueError):
        devig([2.0])


def test_market_rejects_mismatched_price_count():
    with pytest.raises(ValueError):
        Market("x", ["A", "B"], {"book": [2.0]})


def test_best_price_picks_the_highest_odds_and_book():
    m = Market("x", ["A", "B"], {"b1": [2.00, 1.90], "b2": [2.10, 1.85]})
    assert m.best_price(0) == (2.10, "b2")
    assert m.best_price(1) == (1.90, "b1")


def test_margins_reports_each_bookmaker_overround():
    m = Market("x", ["A", "B"], {"sharp": [1.95, 1.95], "soft": [1.85, 1.85]})
    margins = m.margins()
    assert margins["sharp"] == pytest.approx(0.0256, abs=1e-3)
    assert margins["soft"] > margins["sharp"]


def test_efficient_market_yields_no_value():
    m = Market("x", ["A", "B"], {"pinnacle": [1.95, 1.95], "soft": [1.90, 1.90]})
    assert find_value(m, reference_books=["pinnacle"]) == []


def test_soft_book_outlier_is_flagged_as_value():
    m = Market("x", ["A", "B"], {"pinnacle": [1.80, 2.10], "soft": [1.72, 2.35]})
    bets = find_value(m, reference_books=["pinnacle"])
    assert len(bets) == 1
    assert bets[0].selection == "B"
    assert bets[0].book == "soft"
    assert bets[0].ev > 0.05


def test_value_bets_are_sorted_by_edge():
    m = Market(
        "x",
        ["A", "B", "C"],
        {"pinnacle": [2.30, 3.40, 3.20], "soft": [2.20, 3.60, 3.35]},
    )
    bets = find_value(m, reference_books=["pinnacle"])
    assert [b.ev for b in bets] == sorted((b.ev for b in bets), reverse=True)


def test_own_estimate_overrides_the_consensus():
    m = Market("x", ["A", "B"], {"pinnacle": [1.95, 1.95]})
    # Consensus says 50/50 and finds nothing; a 60% estimate finds value.
    assert find_value(m, reference_books=["pinnacle"]) == []
    bets = find_value(m, estimates={"A": 0.60, "B": 0.40}, reference_books=["pinnacle"])
    assert len(bets) == 1
    assert bets[0].selection == "A"
    assert bets[0].ev == pytest.approx(0.60 * 1.95 - 1)


def test_estimates_must_form_a_complete_market():
    m = Market("x", ["A", "B"], {"pinnacle": [1.95, 1.95]})
    with pytest.raises(ValueError):
        find_value(m, estimates={"A": 0.60, "B": 0.60})


def test_estimates_reject_unknown_selection():
    m = Market("x", ["A", "B"], {"pinnacle": [1.95, 1.95]})
    with pytest.raises(KeyError):
        find_value(m, estimates={"A": 0.5, "Z": 0.5})


def test_unknown_reference_book_raises():
    m = Market("x", ["A", "B"], {"pinnacle": [1.95, 1.95]})
    with pytest.raises(KeyError):
        find_value(m, reference_books=["nonexistent"])


def test_min_ev_filters_marginal_bets():
    m = Market("x", ["A", "B"], {"pinnacle": [1.80, 2.10], "soft": [1.72, 2.35]})
    assert find_value(m, reference_books=["pinnacle"], min_ev=0.0)
    assert find_value(m, reference_books=["pinnacle"], min_ev=0.20) == []


def test_stake_follows_kelly_and_bankroll():
    m = Market("x", ["A", "B"], {"pinnacle": [1.80, 2.10], "soft": [1.72, 2.35]})
    half = find_value(m, reference_books=["pinnacle"], bankroll=1000, kelly_multiple=0.5)[0]
    full = find_value(m, reference_books=["pinnacle"], bankroll=1000, kelly_multiple=1.0)[0]
    assert full.stake == pytest.approx(half.stake * 2, rel=1e-3)
