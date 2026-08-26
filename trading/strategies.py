"""A couple of textbook technical rules, implemented plainly so their edge (or
lack of one) can be measured rather than assumed.

Each function returns a position series: 1 = long, 0 = flat, -1 = short,
one entry per input price, using only data available up to that point (no
lookahead -- the whole point of validation.py is to catch it if there were).
"""


def _sma(values: list[float], window: int) -> list[float]:
    out = [None] * len(values)
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= window:
            running -= values[i - window]
        if i >= window - 1:
            out[i] = running / window
    return out


def sma_crossover(closes: list[float], fast: int = 20, slow: int = 50) -> list[int]:
    """Classic trend-following rule: long while the fast average is above the
    slow one, flat otherwise. No shorting -- retail day traders rarely have a
    real edge shorting, and borrow costs make it worse."""
    if fast >= slow:
        raise ValueError("fast window must be shorter than slow window")

    fast_ma = _sma(closes, fast)
    slow_ma = _sma(closes, slow)

    positions = []
    for f, s in zip(fast_ma, slow_ma):
        if f is None or s is None:
            positions.append(0)
        else:
            positions.append(1 if f > s else 0)
    return positions


def _rsi(closes: list[float], period: int) -> list[float]:
    """Wilder's RSI: a simple average to seed it, then exponential smoothing."""
    out = [None] * len(closes)
    if len(closes) <= period:
        return out

    gains = losses = 0.0
    for i in range(1, period + 1):
        change = closes[i] - closes[i - 1]
        gains += max(change, 0.0)
        losses += max(-change, 0.0)
    avg_gain, avg_loss = gains / period, losses / period
    out[period] = _rsi_value(avg_gain, avg_loss)

    for i in range(period + 1, len(closes)):
        change = closes[i] - closes[i - 1]
        gain, loss = max(change, 0.0), max(-change, 0.0)
        avg_gain = (avg_gain * (period - 1) + gain) / period
        avg_loss = (avg_loss * (period - 1) + loss) / period
        out[i] = _rsi_value(avg_gain, avg_loss)

    return out


def _rsi_value(avg_gain: float, avg_loss: float) -> float:
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100.0 - 100.0 / (1.0 + rs)


def rsi_mean_reversion(
    closes: list[float], period: int = 14, buy_below: float = 30.0, sell_above: float = 70.0
) -> list[int]:
    """Classic mean-reversion rule: buy when RSI signals oversold, exit when it
    signals overbought. Stays in the position between those triggers (it does
    not flip short on overbought -- that is a much riskier bet)."""
    rsi = _rsi(closes, period)

    positions = []
    holding = False
    for value in rsi:
        if value is None:
            positions.append(0)
            continue
        if not holding and value < buy_below:
            holding = True
        elif holding and value > sell_above:
            holding = False
        positions.append(1 if holding else 0)
    return positions


def buy_and_hold(closes: list[float]) -> list[int]:
    """The baseline every strategy has to beat, after costs, to be worth the effort."""
    return [1] * len(closes)
