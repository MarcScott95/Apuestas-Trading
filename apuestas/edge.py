"""Where positive expectation actually comes from: the PRICE, not the staking.

A bet has positive expected value when the probability you assign to an outcome
is higher than the probability implied by the price you are offered, after
stripping the bookmaker's margin. Everything else -- progressions, recovery
systems, money management -- operates downstream of this number and cannot
change its sign.

    EV per unit staked = p_true * (decimal_odds - 1) - (1 - p_true)
                       = p_true * decimal_odds - 1

Positive EV therefore requires  p_true > 1 / decimal_odds.
"""

from statistics import NormalDist


def implied_probability(decimal_odds: float) -> float:
    """Probability implied by a price, margin included."""
    if decimal_odds <= 1.0:
        raise ValueError("decimal odds must be > 1.0")
    return 1.0 / decimal_odds


def overround(odds: list[float]) -> float:
    """Bookmaker margin on a complete market.

    Returns the excess over 1.0: a two-way market priced 1.91/1.91 has an
    overround of ~4.7%, which is the hurdle every bet must clear.
    """
    return sum(implied_probability(o) for o in odds) - 1.0


def remove_vig(odds: list[float]) -> list[float]:
    """Fair probabilities implied by a market, with the margin removed
    proportionally (the multiplicative method)."""
    raw = [implied_probability(o) for o in odds]
    total = sum(raw)
    return [r / total for r in raw]


def expected_value(p_true: float, decimal_odds: float) -> float:
    """Expected profit per 1 unit staked. Positive means the bet is worth making."""
    if not 0.0 <= p_true <= 1.0:
        raise ValueError("p_true must be a probability")
    return p_true * decimal_odds - 1.0


def break_even_probability(decimal_odds: float) -> float:
    """The win rate a price demands just to break even."""
    return implied_probability(decimal_odds)


def required_sample_size(
    p_true: float,
    decimal_odds: float,
    alpha: float = 0.05,
    power: float = 0.80,
) -> int:
    """How many bets are needed before a claimed edge is distinguishable from luck.

    This is the question that decides whether you actually have a system or are
    reading noise. Betting results are so high-variance that a genuine 2-3% edge
    takes thousands of bets to demonstrate -- and a losing streak inside that
    sample proves nothing either way.
    """
    b = decimal_odds - 1.0
    q = 1.0 - p_true
    mu = p_true * b - q
    if mu <= 0:
        raise ValueError("no positive edge to detect: p_true is too low for these odds")

    second_moment = p_true * b**2 + q * 1.0
    sigma = (second_moment - mu**2) ** 0.5

    z_alpha = NormalDist().inv_cdf(1 - alpha)      # one-sided
    z_beta = NormalDist().inv_cdf(power)
    n = ((z_alpha + z_beta) * sigma / mu) ** 2
    return int(n) + 1
