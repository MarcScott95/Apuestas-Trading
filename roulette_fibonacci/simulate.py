"""Monte Carlo simulation of the capped-Fibonacci strategy on even-money
roulette bets (18/37 win chance on a European wheel, 18/38 on American).
"""

import argparse
import random
import statistics
from dataclasses import dataclass

from .strategy import FibonacciStrategy

EUROPEAN_WIN_PROB = 18 / 37
AMERICAN_WIN_PROB = 18 / 38


@dataclass
class SessionResult:
    profit: float
    max_drawdown: float
    spins_played: int
    stopped_reason: str  # "take_profit" | "stop_loss" | "max_spins" | "ruin"


def simulate_session(
    win_prob: float,
    unit: float = 1.0,
    max_steps: int = 6,
    bankroll: float = 200.0,
    take_profit: float = 50.0,
    stop_loss: float = 100.0,
    max_spins: int = 500,
    rng: random.Random = None,
) -> SessionResult:
    rng = rng or random
    strategy = FibonacciStrategy(unit=unit, max_steps=max_steps)

    profit = 0.0
    peak = 0.0
    max_drawdown = 0.0
    spins = 0

    while spins < max_spins:
        bet = strategy.current_bet()
        if bet > bankroll + profit:
            return SessionResult(profit, max_drawdown, spins, "ruin")

        won = rng.random() < win_prob
        profit += bet if won else -bet
        strategy.register_result(won)
        spins += 1

        peak = max(peak, profit)
        max_drawdown = max(max_drawdown, peak - profit)

        if profit >= take_profit:
            return SessionResult(profit, max_drawdown, spins, "take_profit")
        if profit <= -stop_loss:
            return SessionResult(profit, max_drawdown, spins, "stop_loss")

    return SessionResult(profit, max_drawdown, spins, "max_spins")


def run_monte_carlo(
    sessions: int,
    win_prob: float,
    unit: float = 1.0,
    max_steps: int = 6,
    bankroll: float = 200.0,
    take_profit: float = 50.0,
    stop_loss: float = 100.0,
    max_spins: int = 500,
    seed: int = None,
) -> dict:
    rng = random.Random(seed)
    results = [
        simulate_session(
            win_prob=win_prob,
            unit=unit,
            max_steps=max_steps,
            bankroll=bankroll,
            take_profit=take_profit,
            stop_loss=stop_loss,
            max_spins=max_spins,
            rng=rng,
        )
        for _ in range(sessions)
    ]

    profits = [r.profit for r in results]
    wins = sum(1 for p in profits if p > 0)
    reasons = {}
    for r in results:
        reasons[r.stopped_reason] = reasons.get(r.stopped_reason, 0) + 1

    return {
        "sessions": sessions,
        "win_rate": wins / sessions,
        "mean_profit": statistics.mean(profits),
        "median_profit": statistics.median(profits),
        "stdev_profit": statistics.pstdev(profits),
        "worst_session": min(profits),
        "best_session": max(profits),
        "mean_max_drawdown": statistics.mean(r.max_drawdown for r in results),
        "stopped_reasons": reasons,
    }


def main():
    parser = argparse.ArgumentParser(description="Monte Carlo test of the capped-Fibonacci roulette strategy")
    parser.add_argument("--wheel", choices=["european", "american"], default="european")
    parser.add_argument("--sessions", type=int, default=5000)
    parser.add_argument("--unit", type=float, default=1.0)
    parser.add_argument("--max-steps", type=int, default=6)
    parser.add_argument("--bankroll", type=float, default=200.0)
    parser.add_argument("--take-profit", type=float, default=50.0)
    parser.add_argument("--stop-loss", type=float, default=100.0)
    parser.add_argument("--max-spins", type=int, default=500)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    win_prob = EUROPEAN_WIN_PROB if args.wheel == "european" else AMERICAN_WIN_PROB

    stats = run_monte_carlo(
        sessions=args.sessions,
        win_prob=win_prob,
        unit=args.unit,
        max_steps=args.max_steps,
        bankroll=args.bankroll,
        take_profit=args.take_profit,
        stop_loss=args.stop_loss,
        max_spins=args.max_spins,
        seed=args.seed,
    )

    print(f"Wheel: {args.wheel} (win prob per spin: {win_prob:.4f})")
    print(f"Sessions simulated: {stats['sessions']}")
    print(f"Sessions ending in profit: {stats['win_rate']:.1%}")
    print(f"Mean profit per session: {stats['mean_profit']:.2f} units")
    print(f"Median profit per session: {stats['median_profit']:.2f} units")
    print(f"Stdev of profit: {stats['stdev_profit']:.2f} units")
    print(f"Best / worst session: {stats['best_session']:.2f} / {stats['worst_session']:.2f} units")
    print(f"Mean max drawdown within a session: {stats['mean_max_drawdown']:.2f} units")
    print(f"Stop reasons: {stats['stopped_reasons']}")


if __name__ == "__main__":
    main()
