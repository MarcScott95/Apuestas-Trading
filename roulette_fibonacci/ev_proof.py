"""Empirical demonstration of the staking-invariance theorem.

Theorem. Let X_i be the result of spin i on an even-money bet (+1 with prob p,
-1 with prob 1-p). Let B_i be the stake on spin i, chosen by ANY rule that
depends only on the history before spin i (any progression, any stop rule, any
amount of cleverness -- just no knowledge of X_i). Then total profit
G_N = sum(B_i * X_i) satisfies

    E[G_N] = E[ sum_i E[B_i * X_i | history] ]
           = E[ sum_i B_i * E[X_i] ]          (B_i is fixed given the history)
           = E[X_1] * E[ sum_i B_i ]
           = -(1/37) * E[total amount staked]

So expected profit is a fixed negative fraction of MONEY WAGERED. Staking
systems only change how much money flows across the table -- they cannot change
the sign of the result. Betting more turns a small negative into a big one.

This module verifies that claim by running structurally different staking
systems and showing they all converge to the same profit/wagered ratio.
"""

import argparse
import random

from .labouchere import Labouchere
from .strategy import FibonacciStrategy

EUROPEAN_WIN_PROB = 18 / 37


def _flat(rng, spins, win_prob):
    profit = wagered = 0.0
    for _ in range(spins):
        bet = 1.0
        wagered += bet
        profit += bet if rng.random() < win_prob else -bet
    return profit, wagered


def _martingale(rng, spins, win_prob, cap=1024.0):
    profit = wagered = 0.0
    bet = 1.0
    for _ in range(spins):
        wagered += bet
        if rng.random() < win_prob:
            profit += bet
            bet = 1.0
        else:
            profit -= bet
            bet = min(bet * 2, cap)
    return profit, wagered


def _fibonacci_capped(rng, spins, win_prob):
    profit = wagered = 0.0
    system = FibonacciStrategy(unit=1.0, max_steps=6)
    for _ in range(spins):
        bet = system.current_bet()
        wagered += bet
        won = rng.random() < win_prob
        profit += bet if won else -bet
        system.register_result(won)
    return profit, wagered


def _labouchere(rng, spins, win_prob, cap=1024.0):
    profit = wagered = 0.0
    system = Labouchere(target=1, unit=1.0)
    for _ in range(spins):
        if system.complete:
            system = Labouchere(target=1, unit=1.0)
        bet = min(system.current_bet(), cap)
        wagered += bet
        won = rng.random() < win_prob
        profit += bet if won else -bet
        system.register_result(won)
    return profit, wagered


def _random_stakes(rng, spins, win_prob):
    """Deliberately senseless staking, to show even randomness obeys the rule."""
    profit = wagered = 0.0
    for _ in range(spins):
        bet = rng.choice([1.0, 3.0, 7.0, 25.0, 100.0])
        wagered += bet
        profit += bet if rng.random() < win_prob else -bet
    return profit, wagered


def _chase_the_streak(rng, spins, win_prob):
    """Bet bigger after wins ('ride the hot streak') -- the opposite instinct."""
    profit = wagered = 0.0
    bet = 1.0
    for _ in range(spins):
        wagered += bet
        if rng.random() < win_prob:
            profit += bet
            bet = min(bet * 2, 256.0)
        else:
            profit -= bet
            bet = 1.0
    return profit, wagered


SYSTEMS = {
    "Flat (always 1u)": _flat,
    "Martingale": _martingale,
    "Fibonacci capped at 6": _fibonacci_capped,
    "Labouchere (+1u target)": _labouchere,
    "Random stake sizes": _random_stakes,
    "Chase the hot streak": _chase_the_streak,
}


def main():
    parser = argparse.ArgumentParser(description="Show that staking cannot change expected value")
    parser.add_argument("--spins", type=int, default=2_000_000)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    win_prob = EUROPEAN_WIN_PROB
    theoretical = -1 / 37

    print(f"European wheel, {args.spins:,} spins per system, win prob {win_prob:.4f}")
    print(f"Theoretical edge on every unit wagered: {theoretical:+.4%}\n")
    print(f"{'System':<26}{'Profit':>14}{'Wagered':>16}{'Profit/Wagered':>17}")
    print("-" * 73)

    for name, fn in SYSTEMS.items():
        rng = random.Random(args.seed)
        profit, wagered = fn(rng, args.spins, win_prob)
        print(f"{name:<26}{profit:>14,.0f}{wagered:>16,.0f}{profit / wagered:>16.3%}")

    print("-" * 73)
    print(f"{'THEORY':<26}{'':>14}{'':>16}{theoretical:>16.3%}")
    print(
        "\nEvery system lands on the same ratio. The only column a staking plan\n"
        "controls is 'Wagered' -- and multiplying that number only multiplies the loss."
    )


if __name__ == "__main__":
    main()
