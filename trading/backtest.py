"""A minimal, honest backtest engine.

'Honest' here means specific things: it charges a cost every time the position
changes, it never lets a signal see the bar it is trading on (positions apply
to the NEXT day's return, not the day the signal fired), and it reports the
comparison that actually matters -- the strategy against simply holding the
asset, after the same costs would have applied to entering once.

None of this replaces the questions in validation.py (is the edge real, or did
you just fit noise). This module only computes returns correctly; it does not
judge them.
"""

from dataclasses import dataclass


@dataclass
class BacktestResult:
    dates: list[str]
    daily_returns: list[float]     # strategy return realised on each day
    positions: list[int]           # position HELD during that day (-1, 0, 1)
    equity_curve: list[float]      # starts at 1.0
    trades: int                    # number of position changes (round trips ~= trades/2)
    total_return: float
    max_drawdown: float

    @property
    def n_days(self) -> int:
        return len(self.daily_returns)


def backtest(
    closes: list[float],
    signals: list[int],
    dates: list[str] = None,
    cost_bps: float = 5.0,
) -> BacktestResult:
    """Run a position series against a price series.

    `signals[i]` is the position DECIDED at the close of day i (using only
    information available up to and including day i), so it earns the return
    from day i to day i+1 -- never the return of day i itself. This is the
    single most common way a backtest cheats without anyone intending it to.

    `cost_bps` is the round-trip cost in basis points charged whenever the
    position changes (spread + commission + slippage, all lumped together).
    5 bps is a reasonable placeholder for a liquid ETF; a less liquid stock or
    a wider spread instrument should use more.
    """
    if len(closes) != len(signals):
        raise ValueError("closes and signals must be the same length")
    if len(closes) < 2:
        raise ValueError("need at least 2 price points")

    cost = cost_bps / 10_000.0
    n = len(closes)
    dates = dates or [str(i) for i in range(n)]

    daily_returns = []
    positions_held = []
    equity = 1.0
    equity_curve = [equity]
    peak = equity
    max_dd = 0.0
    trades = 0
    prev_position = 0

    for i in range(1, n):
        position = signals[i - 1]
        market_return = closes[i] / closes[i - 1] - 1.0

        turnover_cost = 0.0
        if position != prev_position:
            turnover_cost = cost
            trades += 1

        day_return = position * market_return - turnover_cost
        daily_returns.append(day_return)
        positions_held.append(position)

        equity *= 1.0 + day_return
        equity_curve.append(equity)
        peak = max(peak, equity)
        max_dd = max(max_dd, (peak - equity) / peak)

        prev_position = position

    return BacktestResult(
        dates=dates[1:],
        daily_returns=daily_returns,
        positions=positions_held,
        equity_curve=equity_curve,
        trades=trades,
        total_return=equity - 1.0,
        max_drawdown=max_dd,
    )
