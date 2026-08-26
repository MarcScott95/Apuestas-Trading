"""Why closing line value answers the '15,000 bets' problem.

Earlier we showed that proving a 2% edge from profit alone needs ~15,000 bets.
That is true, and it is a serious practical obstacle: nobody wants to bet for
three years before learning whether their method works.

CLV escapes it. The reason is that profit and CLV measure the same edge with
wildly different amounts of noise:

    profit per bet:  either +(odds-1) or -1   -> standard deviation ~1.0
    CLV per bet:     odds_taken / odds_close  -> standard deviation ~0.04

Both have the same mean (if the closing line is efficient, your expected ROI
IS your average CLV). But the signal-to-noise ratio differs by a factor of ~25,
and required sample size scales with the SQUARE of that ratio.

This module simulates a bettor with a real edge and measures how many bets each
metric needs before it can tell that the edge is there.
"""

import argparse
import math
import random
from statistics import NormalDist

CHECKPOINTS = [25, 50, 100, 200, 400, 800, 1600, 3200, 6400, 12800, 25600]


def _t_stat(values: list[float]) -> float:
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    if var <= 0:
        return float("inf") if mean > 0 else 0.0
    return mean / math.sqrt(var / n)


def simulate_bettor(
    n_bets: int,
    mean_clv: float,
    clv_sd: float,
    rng: random.Random,
) -> tuple[list[float], list[float]]:
    """A bettor who beats the closing line by `mean_clv` on average.

    The closing line is assumed efficient, so the true probability of each bet
    is exactly what the closing price implies. The bettor's edge comes entirely
    from having taken a better price earlier -- which is what CLV measures and
    what a genuine edge actually looks like.
    """
    returns, clvs = [], []
    for _ in range(n_bets):
        p_true = rng.uniform(0.35, 0.65)
        closing_odds = 1.0 / p_true

        clv = rng.gauss(mean_clv, clv_sd)
        odds_taken = closing_odds * (1.0 + clv)

        won = rng.random() < p_true
        returns.append(odds_taken - 1.0 if won else -1.0)
        clvs.append(clv)

    return returns, clvs


def first_detection(values: list[float], z: float) -> int:
    """First checkpoint at which the metric is significantly positive."""
    for n in CHECKPOINTS:
        if n > len(values):
            break
        if _t_stat(values[:n]) > z:
            return n
    return 0  # never detected within the simulated horizon


def main():
    parser = argparse.ArgumentParser(description="CLV vs ROI: which detects an edge sooner")
    parser.add_argument("--edge", type=float, default=0.03, help="true edge / mean CLV")
    parser.add_argument("--clv-sd", type=float, default=0.04, help="bet-to-bet CLV variation")
    parser.add_argument("--trials", type=int, default=2000)
    parser.add_argument("--bets", type=int, default=25600)
    parser.add_argument("--alpha", type=float, default=0.05)
    parser.add_argument("--seed", type=int, default=3)
    args = parser.parse_args()

    z = NormalDist().inv_cdf(1 - args.alpha)
    rng = random.Random(args.seed)

    roi_detect, clv_detect = [], []
    roi_hits = {n: 0 for n in CHECKPOINTS}
    clv_hits = {n: 0 for n in CHECKPOINTS}

    for _ in range(args.trials):
        returns, clvs = simulate_bettor(args.bets, args.edge, args.clv_sd, rng)
        roi_detect.append(first_detection(returns, z))
        clv_detect.append(first_detection(clvs, z))
        for n in CHECKPOINTS:
            if n <= args.bets:
                if _t_stat(returns[:n]) > z:
                    roi_hits[n] += 1
                if _t_stat(clvs[:n]) > z:
                    clv_hits[n] += 1

    print(f"Apostante con ventaja real del {args.edge:.1%} (CLV medio), sd por apuesta {args.clv_sd:.1%}")
    print(f"{args.trials} simulaciones, confianza {1 - args.alpha:.0%}\n")

    print(f"{'Apuestas':>10}{'Detecta por ROI':>20}{'Detecta por CLV':>20}")
    print("-" * 50)
    for n in CHECKPOINTS:
        if n > args.bets:
            break
        print(f"{n:>10,}{roi_hits[n] / args.trials:>19.1%}{clv_hits[n] / args.trials:>20.1%}")
    print("-" * 50)

    roi_ok = [d for d in roi_detect if d]
    clv_ok = [d for d in clv_detect if d]
    roi_ok.sort()
    clv_ok.sort()

    def median(xs):
        return xs[len(xs) // 2] if xs else None

    print(f"\nMediana de apuestas hasta detectar la ventaja:")
    print(f"  por ROI: {median(roi_ok):,}" if roi_ok else "  por ROI: no detectada")
    print(f"  por CLV: {median(clv_ok):,}" if clv_ok else "  por CLV: no detectada")
    if roi_ok and clv_ok and median(clv_ok):
        print(f"\n  El CLV lo detecta ~{median(roi_ok) / median(clv_ok):.0f}x antes.")
    print(
        "\nPor eso se registra la cuota de cierre: dice si estas apostando bien\n"
        "cientos de apuestas antes de que el beneficio pueda decirtelo."
    )


if __name__ == "__main__":
    main()
