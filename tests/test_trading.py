import pytest

from trading.backtest import backtest
from trading.strategies import buy_and_hold, sma_crossover, rsi_mean_reversion
from trading.validation import validate
from trading.martingale_demo import simulate_martingale_buyer, simulate_fixed_position


def test_buy_and_hold_matches_raw_return_minus_one_entry_cost():
    closes = [100.0, 110.0, 121.0]
    result = backtest(closes, buy_and_hold(closes), cost_bps=0.0)
    assert result.total_return == pytest.approx(121 / 100 - 1)
    assert result.trades == 1  # entering from flat counts as one position change


def test_flat_position_earns_nothing():
    closes = [100.0, 110.0, 90.0]
    result = backtest(closes, [0, 0, 0], cost_bps=0.0)
    assert result.total_return == 0.0
    assert result.trades == 0


def test_signal_applies_to_the_next_bar_not_the_current_one():
    """The core no-lookahead guarantee: a signal formed on day i must not earn
    day i's own return."""
    closes = [100.0, 200.0, 200.0]  # huge jump on day 1
    # Signal only goes long AFTER seeing the jump (day 1 onward).
    result = backtest(closes, [0, 1, 1], cost_bps=0.0)
    # Day1->2 return is 0%, so a lookahead-free engine earns ~0, not the 100% jump.
    assert result.total_return == pytest.approx(0.0, abs=1e-9)


def test_cost_is_charged_only_on_position_changes():
    closes = [100.0, 100.0, 100.0, 100.0]
    result = backtest(closes, [1, 1, 1, 1], cost_bps=10.0)
    assert result.trades == 1
    assert result.total_return == pytest.approx(-0.001, abs=1e-9)


def test_drawdown_is_measured_from_the_running_peak():
    closes = [100.0, 120.0, 90.0, 100.0]
    result = backtest(closes, [1, 1, 1, 1], cost_bps=0.0)
    assert result.max_drawdown == pytest.approx(1 - 90 / 120, abs=1e-6)


def test_backtest_rejects_mismatched_lengths():
    with pytest.raises(ValueError):
        backtest([1.0, 2.0], [0, 0, 0])


def test_sma_crossover_requires_fast_shorter_than_slow():
    with pytest.raises(ValueError):
        sma_crossover([1.0] * 10, fast=50, slow=20)


def test_sma_crossover_flat_before_enough_data():
    closes = [float(i) for i in range(1, 10)]
    positions = sma_crossover(closes, fast=3, slow=5)
    assert positions[:4] == [0, 0, 0, 0]


def test_sma_crossover_goes_long_on_an_uptrend():
    closes = [100.0 + i for i in range(60)]  # steady uptrend
    positions = sma_crossover(closes, fast=5, slow=20)
    assert positions[-1] == 1


def test_sma_crossover_stays_flat_on_a_downtrend():
    closes = [200.0 - i for i in range(60)]
    positions = sma_crossover(closes, fast=5, slow=20)
    assert positions[-1] == 0


def test_rsi_mean_reversion_buys_after_a_sharp_drop():
    closes = [100.0] * 15 + [90.0, 80.0, 70.0]  # sudden decline -> oversold
    positions = rsi_mean_reversion(closes, period=14, buy_below=30, sell_above=70)
    assert positions[-1] == 1


def test_rsi_mean_reversion_stays_flat_without_a_trigger():
    closes = [100.0 + (i % 2) for i in range(30)]  # flat chop, no real move
    positions = rsi_mean_reversion(closes, period=14)
    assert positions[-1] == 0


def test_validate_flags_pure_overfitting():
    """A rule that only works on the exact noise it was tested on should not
    survive being split into two halves."""
    in_sample = [100.0 + i for i in range(60)]      # uptrend
    out_sample = [160.0 - i for i in range(60)]     # then a reversal
    closes = in_sample + out_sample

    report = validate("TEST", "SMA 5/20", closes, lambda c: sma_crossover(c, 5, 20))
    assert report.in_sample_return > 0
    assert report.out_sample_return < report.in_sample_return


def test_validate_buy_and_hold_matches_itself():
    closes = [100.0 + i * 0.5 for i in range(120)]
    report = validate("TEST", "Buy&Hold", closes, buy_and_hold)
    assert report.out_sample_return == pytest.approx(report.buy_hold_out_sample_return, abs=1e-9)
    assert report.beats_buy_hold_out_sample is False


def test_martingale_survives_a_flat_market():
    closes = [100.0] * 50
    result = simulate_martingale_buyer(closes, initial_position=10, add_on_drop_pct=0.05)
    assert not result.margin_called


def test_martingale_gets_margin_called_on_a_sustained_decline():
    """The whole point: a real, persistent downtrend blows up a doubling
    strategy well before it could recover, unlike an independent coin flip."""
    closes = [100.0 * (0.97 ** i) for i in range(150)]  # steady ~3%/step decline
    result = simulate_martingale_buyer(
        closes, initial_position=10, add_on_drop_pct=0.03, max_leverage=10.0
    )
    assert result.margin_called
    assert result.margin_call_day > 0


def test_fixed_position_never_exceeds_initial_exposure():
    closes = [100.0 * (0.97 ** i) for i in range(150)]
    equity = simulate_fixed_position(closes, position=10.0, account_equity=100.0)
    # No doubling down: worst case is losing the whole initial stake, not more.
    assert min(equity) >= 100.0 - 10.0 - 1e-9


def test_martingale_loses_more_than_fixed_position_in_a_downtrend():
    closes = [100.0 * (0.98 ** i) for i in range(100)]
    grid = simulate_martingale_buyer(closes, initial_position=10, add_on_drop_pct=0.05, max_leverage=50.0)
    flat = simulate_fixed_position(closes, position=10.0)
    assert grid.equity_curve[-1] < flat[-1]
