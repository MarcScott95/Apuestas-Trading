import math

import pytest

from apuestas.edge import (
    break_even_probability,
    expected_value,
    implied_probability,
    overround,
    remove_vig,
    required_sample_size,
)
from apuestas.kelly import growth_rate, kelly_fraction
from apuestas.wheel_bias import break_even_pocket_probability, straight_up_ev


def test_implied_probability():
    assert implied_probability(2.0) == 0.5
    assert implied_probability(4.0) == 0.25


def test_overround_detects_bookmaker_margin():
    # A fair coin market would be 2.0/2.0; 1.91/1.91 carries the vig.
    assert overround([2.0, 2.0]) == pytest.approx(0.0)
    assert overround([1.91, 1.91]) == pytest.approx(0.0471, abs=1e-4)


def test_remove_vig_returns_normalised_probabilities():
    fair = remove_vig([1.91, 1.91])
    assert sum(fair) == pytest.approx(1.0)
    assert fair[0] == pytest.approx(0.5)


def test_expected_value_sign_matches_price():
    assert expected_value(0.55, 2.0) == pytest.approx(0.10)
    assert expected_value(0.50, 2.0) == pytest.approx(0.0)
    assert expected_value(0.45, 2.0) == pytest.approx(-0.10)


def test_roulette_even_money_is_negative_ev():
    assert expected_value(18 / 37, 2.0) < 0


def test_break_even_probability_is_inverse_odds():
    assert break_even_probability(2.0) == 0.5
    assert break_even_probability(1.5) == pytest.approx(2 / 3)


def test_kelly_fraction_matches_closed_form():
    # p=0.55 at even money -> f* = 2p - 1 = 0.10
    assert kelly_fraction(0.55, 2.0) == pytest.approx(0.10)


def test_kelly_returns_zero_without_an_edge():
    assert kelly_fraction(18 / 37, 2.0) == 0.0
    assert kelly_fraction(0.50, 2.0) == 0.0


def test_fractional_kelly_scales_the_stake():
    assert kelly_fraction(0.55, 2.0, fraction=0.5) == pytest.approx(0.05)


def test_growth_rate_is_maximised_at_the_kelly_fraction():
    p, odds = 0.55, 2.0
    f_star = kelly_fraction(p, odds)
    best = growth_rate(p, odds, f_star)
    for delta in (-0.04, -0.02, 0.02, 0.04):
        assert growth_rate(p, odds, f_star + delta) < best


def test_growth_rate_negative_when_overbetting():
    # Betting far above Kelly turns a winning edge into geometric decay.
    assert growth_rate(0.55, 2.0, 0.5) < 0


def test_required_sample_size_grows_as_edge_shrinks():
    big_edge = required_sample_size(0.60, 2.0)
    small_edge = required_sample_size(0.52, 2.0)
    assert small_edge > big_edge
    assert small_edge > 1000


def test_required_sample_size_rejects_absent_edge():
    with pytest.raises(ValueError):
        required_sample_size(18 / 37, 2.0)


def test_roulette_straight_up_break_even_is_one_in_36():
    assert break_even_pocket_probability() == pytest.approx(1 / 36)
    assert straight_up_ev(1 / 37) == pytest.approx(-1 / 37)
    assert straight_up_ev(1 / 36) == pytest.approx(0.0, abs=1e-12)
