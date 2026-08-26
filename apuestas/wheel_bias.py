"""The only mechanism that produces positive expectation at a roulette table.

Since expected value is fixed at -(1/37) * amount wagered for ANY staking rule,
the sole way to reach positive EV is to change the probabilities themselves --
i.e. to find a wheel whose pockets are not equally likely, because it is
physically imperfect (worn frets, a tilted rotor, a deformed ball track).

A straight-up number pays 35:1, so:
    EV = p * 35 - (1 - p) = 36p - 1
    break-even p = 1/36 = 0.02778
    fair wheel   p = 1/37 = 0.02703

The gap is tiny: a pocket must beat 1-in-36 rather than 1-in-37. This module
answers the practical question -- how many spins must you record before a
frequency that high is evidence of a real bias rather than ordinary noise?

The answer is what makes this approach mostly historical: casinos rebalance and
rotate wheels, and modern manufacturing tolerances are far tighter than in the
era when this was profitable. It is presented here because it is the honest
answer to "is there any +EV roulette strategy" -- and because it shows the work
is statistical observation, never bet sizing.
"""

import argparse
from statistics import NormalDist

POCKETS_EUROPEAN = 37
STRAIGHT_UP_PAYOUT = 35


def straight_up_ev(p: float) -> float:
    """Expected profit per unit on a single-number bet at true probability p."""
    return p * STRAIGHT_UP_PAYOUT - (1 - p)


def break_even_pocket_probability() -> float:
    return 1.0 / (STRAIGHT_UP_PAYOUT + 1)


def spins_to_detect_bias(
    biased_p: float,
    fair_p: float = 1.0 / POCKETS_EUROPEAN,
    alpha: float = 0.05,
    power: float = 0.80,
    pockets_scanned: int = POCKETS_EUROPEAN,
) -> int:
    """Spins needed to establish that one pocket is genuinely hot.

    `pockets_scanned` applies a Bonferroni correction: if you watch all 37
    pockets and report whichever looks hottest, you get 37 chances to be fooled
    by noise, so the significance threshold must tighten accordingly. Skipping
    this correction is the classic error that makes random wheels look biased.
    """
    if biased_p <= fair_p:
        raise ValueError("biased_p must exceed the fair probability")

    adjusted_alpha = alpha / max(1, pockets_scanned)
    z_alpha = NormalDist().inv_cdf(1 - adjusted_alpha)
    z_beta = NormalDist().inv_cdf(power)

    se_null = (fair_p * (1 - fair_p)) ** 0.5
    se_alt = (biased_p * (1 - biased_p)) ** 0.5
    n = ((z_alpha * se_null + z_beta * se_alt) / (biased_p - fair_p)) ** 2
    return int(n) + 1


def main():
    parser = argparse.ArgumentParser(description="Feasibility of biased-wheel advantage play")
    parser.add_argument("--spins-per-hour", type=float, default=40.0)
    args = parser.parse_args()

    fair = 1.0 / POCKETS_EUROPEAN
    breakeven = break_even_pocket_probability()

    print("Single-number bet on a European wheel (pays 35:1)\n")
    print(f"  Fair pocket probability:       1/37 = {fair:.5f}  -> EV {straight_up_ev(fair):+.4%}")
    print(f"  Break-even pocket probability: 1/36 = {breakeven:.5f}  -> EV {straight_up_ev(breakeven):+.4%}")
    print("\nA pocket must hit more often than 1-in-36 before betting it is profitable.\n")

    print(f"{'Bias level':<16}{'p':>10}{'Edge':>10}{'Spins to prove':>18}{'Hours watching':>17}")
    print("-" * 71)
    for label, denom in [("1 in 35", 35), ("1 in 34", 34), ("1 in 33", 33), ("1 in 30", 30)]:
        p = 1.0 / denom
        spins = spins_to_detect_bias(p)
        hours = spins / args.spins_per_hour
        print(f"{label:<16}{p:>10.5f}{straight_up_ev(p):>+10.2%}{spins:>18,}{hours:>17,.0f}")
    print("-" * 71)
    print(
        "\nThe edge is real when the bias is real -- but confirming it takes hundreds of\n"
        "hours of recorded spins on ONE wheel, before betting a single unit. The work is\n"
        "data collection, not money management."
    )


if __name__ == "__main__":
    main()
