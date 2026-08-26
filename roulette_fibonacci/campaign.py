"""Simulate the exact plan: 'win +1 unit per session, accumulate them, and
accept that a bad session needs X later wins to recover'.

Each session runs a Labouchere line until it either reaches the target (+1
unit) or is stopped by a real-world constraint: the table maximum, or the
bankroll. Those constraints are not optional details -- they are the whole
reason the plan cannot work, so they are modelled explicitly.
"""

import argparse
import random
import statistics
from dataclasses import dataclass

from .labouchere import Labouchere

EUROPEAN_WIN_PROB = 18 / 37
AMERICAN_WIN_PROB = 18 / 38


@dataclass
class SessionOutcome:
    profit: float
    wagered: float
    spins: int
    reached_target: bool


def play_session(
    win_prob: float,
    target: int = 1,
    unit: float = 1.0,
    table_max: float = 500.0,
    session_bankroll: float = 1000.0,
    rng: random.Random = None,
) -> SessionOutcome:
    rng = rng or random
    system = Labouchere(target=target, unit=unit)

    profit = 0.0
    wagered = 0.0
    spins = 0

    while not system.complete:
        bet = system.current_bet()

        # Real-world stops: the table will not take the bet, or you cannot fund it.
        if bet > table_max or bet > session_bankroll + profit:
            return SessionOutcome(profit, wagered, spins, reached_target=False)

        won = rng.random() < win_prob
        wagered += bet
        profit += bet if won else -bet
        system.register_result(won)
        spins += 1

    return SessionOutcome(profit, wagered, spins, reached_target=True)


@dataclass
class CampaignResult:
    final_profit: float
    total_wagered: float
    sessions_won: int
    sessions_lost: int
    blowup_loss_total: float
    worst_session: float
    total_spins: int


def run_campaign(
    sessions: int,
    win_prob: float,
    target: int = 1,
    unit: float = 1.0,
    table_max: float = 500.0,
    session_bankroll: float = 1000.0,
    rng: random.Random = None,
) -> CampaignResult:
    rng = rng or random
    profit = 0.0
    wagered = 0.0
    spins = 0
    won = lost = 0
    blowup_loss_total = 0.0
    worst = 0.0

    for _ in range(sessions):
        outcome = play_session(
            win_prob=win_prob,
            target=target,
            unit=unit,
            table_max=table_max,
            session_bankroll=session_bankroll,
            rng=rng,
        )
        profit += outcome.profit
        wagered += outcome.wagered
        spins += outcome.spins
        if outcome.reached_target:
            won += 1
        else:
            lost += 1
            blowup_loss_total += outcome.profit
        worst = min(worst, outcome.profit)

    return CampaignResult(profit, wagered, won, lost, blowup_loss_total, worst, spins)


def main():
    parser = argparse.ArgumentParser(
        description="Simulate the 'accumulate +1 unit per session' roulette plan"
    )
    parser.add_argument("--wheel", choices=["european", "american"], default="european")
    parser.add_argument("--campaigns", type=int, default=2000)
    parser.add_argument("--sessions", type=int, default=200, help="sessions per campaign")
    parser.add_argument("--target", type=int, default=1, help="units targeted per session")
    parser.add_argument("--unit", type=float, default=1.0)
    parser.add_argument("--table-max", type=float, default=500.0)
    parser.add_argument("--session-bankroll", type=float, default=1000.0)
    parser.add_argument("--seed", type=int, default=None)
    args = parser.parse_args()

    win_prob = EUROPEAN_WIN_PROB if args.wheel == "european" else AMERICAN_WIN_PROB
    rng = random.Random(args.seed)

    results = [
        run_campaign(
            sessions=args.sessions,
            win_prob=win_prob,
            target=args.target,
            unit=args.unit,
            table_max=args.table_max,
            session_bankroll=args.session_bankroll,
            rng=rng,
        )
        for _ in range(args.campaigns)
    ]

    profits = [r.final_profit for r in results]
    total_sessions = args.campaigns * args.sessions
    sessions_won = sum(r.sessions_won for r in results)
    total_wagered = sum(r.total_wagered for r in results)
    total_profit = sum(profits)

    print(f"Wheel: {args.wheel} (win prob per spin: {win_prob:.4f})")
    print(f"Campaigns: {args.campaigns} x {args.sessions} sessions each")
    print()
    sessions_lost = sum(r.sessions_lost for r in results)
    blowup_total = sum(r.blowup_loss_total for r in results)
    mean_blowup = blowup_total / sessions_lost if sessions_lost else 0.0

    print(f"Session hit rate (+{args.target}u reached): {sessions_won / total_sessions:.2%}")
    print(f"Sessions that blew up: {sessions_lost / total_sessions:.2%}")
    print(f"Mean loss when a session blows up: {mean_blowup:,.0f} units")
    print(f"Worst single session seen: {min(r.worst_session for r in results):,.0f} units")
    print()
    print("  Per-session arithmetic:")
    print(f"    win  {sessions_won / total_sessions:.4f} x +{args.target}u      = {sessions_won * args.target / total_sessions:+.4f} u")
    print(f"    lose {sessions_lost / total_sessions:.4f} x {mean_blowup:,.0f}u = {blowup_total / total_sessions:+.4f} u")
    print(f"    net expected value per session  = {total_profit / total_sessions:+.4f} u")
    print()
    print(f"Campaigns ending in profit: {sum(1 for p in profits if p > 0) / len(profits):.2%}")
    print(f"Mean campaign profit: {statistics.mean(profits):.2f} units")
    print(f"Median campaign profit: {statistics.median(profits):.2f} units")
    print(f"Best / worst campaign: {max(profits):.0f} / {min(profits):.0f} units")
    print()
    print(f"Total wagered across all campaigns: {total_wagered:,.0f} units")
    print(f"Total profit: {total_profit:,.0f} units")
    print(f"Profit / wagered: {total_profit / total_wagered:+.4%}")
    print(f"House edge for this wheel:       {-(1 / 37 if args.wheel == 'european' else 2 / 38):+.4%}")


if __name__ == "__main__":
    main()
