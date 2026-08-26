"""Kelly staking: the correct answer to 'grow the bankroll steadily, compound
the wins, and survive the drawdowns'.

Kelly is what the user's plan was reaching for. It delivers, genuinely:
  - profit that compounds instead of accumulating linearly,
  - stakes that rise automatically as the bankroll rises,
  - mathematical impossibility of ruin (you always bet a FRACTION, never a
    fixed amount, so a losing run shrinks the stake instead of escalating it),
  - recovery after a drawdown without any 'chase' mechanic.

But it inverts the dependency of a progression system. A progression asks
"how do I size bets so that losses get repaid?" Kelly asks "given a real edge,
what fraction maximises long-run growth?" With edge <= 0, the Kelly fraction is
zero or negative: the maths instructs you not to bet. That is not a limitation
of Kelly -- it is the same theorem as ev_proof.py, arriving from the other side.

    f* = (p * b - q) / b        where b = decimal_odds - 1

f* is the fraction of the CURRENT bankroll to stake.
"""

import argparse
import math
import random
import statistics


def kelly_fraction(p: float, decimal_odds: float, fraction: float = 1.0) -> float:
    """Optimal stake as a fraction of bankroll. Returns 0.0 when there is no edge.

    `fraction` applies fractional Kelly (0.5 = 'half Kelly'), which is what
    practitioners actually use: it gives up 25% of the growth rate for roughly
    half the volatility, and protects against overestimating your own edge.
    """
    b = decimal_odds - 1.0
    if b <= 0:
        raise ValueError("decimal odds must be > 1.0")
    q = 1.0 - p
    f = (p * b - q) / b
    return max(0.0, f * fraction)


def growth_rate(p: float, decimal_odds: float, f: float) -> float:
    """Expected logarithmic growth per bet at stake fraction f.

    This is the quantity Kelly maximises. Negative means the bankroll shrinks
    geometrically even if individual bets sometimes win.
    """
    b = decimal_odds - 1.0
    q = 1.0 - p
    if f >= 1.0 or (1 - f) <= 0:
        return float("-inf")
    return p * math.log(1 + f * b) + q * math.log(1 - f)


def simulate_bankroll(
    bets: int,
    p: float,
    decimal_odds: float,
    kelly_multiple: float = 0.5,
    start_bankroll: float = 1000.0,
    min_stake: float = 1.0,
    rng: random.Random = None,
) -> dict:
    """Run a bankroll through `bets` wagers using fractional Kelly staking."""
    rng = rng or random
    f = kelly_fraction(p, decimal_odds, kelly_multiple)
    b = decimal_odds - 1.0

    bankroll = start_bankroll
    peak = bankroll
    max_dd = 0.0
    busted = False

    for _ in range(bets):
        stake = bankroll * f
        if stake < min_stake:
            busted = True
            break
        if rng.random() < p:
            bankroll += stake * b
        else:
            bankroll -= stake
        peak = max(peak, bankroll)
        max_dd = max(max_dd, (peak - bankroll) / peak)

    return {
        "final_bankroll": bankroll,
        "growth_multiple": bankroll / start_bankroll,
        "max_drawdown_pct": max_dd,
        "stake_fraction": f,
        "below_min_stake": busted,
    }


def main():
    parser = argparse.ArgumentParser(description="Kelly staking behaviour under a real edge")
    parser.add_argument("--p", type=float, default=0.55, help="your true win probability")
    parser.add_argument("--odds", type=float, default=2.0, help="decimal odds offered")
    parser.add_argument("--bets", type=int, default=1000)
    parser.add_argument("--runs", type=int, default=5000)
    parser.add_argument("--kelly", type=float, default=0.5, help="Kelly multiple (0.5 = half Kelly)")
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()

    ev = args.p * args.odds - 1.0
    full_f = kelly_fraction(args.p, args.odds, 1.0)
    used_f = kelly_fraction(args.p, args.odds, args.kelly)

    print(f"Win probability: {args.p:.4f}   Decimal odds: {args.odds}")
    print(f"Break-even probability at these odds: {1 / args.odds:.4f}")
    print(f"Edge (EV per unit staked): {ev:+.4%}")
    print()

    if ev <= 0:
        print("Kelly fraction: 0.0000 -- no edge, the correct stake is nothing.")
        print("No staking plan can repair this. See roulette_fibonacci/ev_proof.py.")
        return

    print(f"Full Kelly stake: {full_f:.2%} of bankroll per bet")
    print(f"Using {args.kelly:g}x Kelly: {used_f:.2%} of bankroll per bet")
    print(f"Expected log-growth per bet: {growth_rate(args.p, args.odds, used_f):+.5f}")
    print()

    rng = random.Random(args.seed)
    results = [
        simulate_bankroll(
            bets=args.bets,
            p=args.p,
            decimal_odds=args.odds,
            kelly_multiple=args.kelly,
            start_bankroll=args.bankroll,
            rng=rng,
        )
        for _ in range(args.runs)
    ]

    multiples = [r["growth_multiple"] for r in results]
    print(f"After {args.bets} bets, across {args.runs} simulated runs:")
    print(f"  Median bankroll multiple: {statistics.median(multiples):.2f}x")
    print(f"  Runs that ended up: {sum(1 for m in multiples if m > 1) / len(multiples):.1%}")
    print(f"  Worst run: {min(multiples):.2f}x    Best run: {max(multiples):.2f}x")
    print(f"  Mean max drawdown: {statistics.mean(r['max_drawdown_pct'] for r in results):.1%}")
    print(f"  Runs that fell below the minimum stake: {sum(1 for r in results if r['below_min_stake'])}")


if __name__ == "__main__":
    main()
