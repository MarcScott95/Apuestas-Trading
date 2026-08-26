"""Bet log and edge validation.

Finding a value bet is easy; knowing whether your edge is real is the hard part,
and it is the part almost everyone skips. This module keeps a permanent record
of every bet and answers one question honestly:

    Is my profit evidence of an edge, or is it noise?

It tracks two independent measures:

ROI (return on investment)
    What you actually earned. It is what matters, but it is extremely noisy:
    demonstrating a genuine 2% edge takes ~15,000 bets before profit alone can
    distinguish you from a lucky coin.

CLV (closing line value)
    Whether the price you took beat the market's final price before kickoff.
    The closing line is the market's best and most-informed estimate, so beating
    it consistently is evidence you are pricing better than the market -- and
    crucially, CLV is far less noisy than profit, because it is not contaminated
    by whether the ball happened to go in.

CLV is the reason the 15,000-bet problem is survivable in practice: it can tell
you that you are betting well after a few hundred bets, long before your profit
curve could. A bettor with good CLV and bad short-run results is unlucky; one
with bad CLV and good results is lucky, and will regress.
"""

import argparse
import csv
import math
import os
from dataclasses import asdict, dataclass, fields
from datetime import date
from statistics import NormalDist

FIELDNAMES = [
    "bet_id",
    "date",
    "event",
    "selection",
    "book",
    "odds_taken",
    "p_estimate",
    "stake",
    "ev_pct",
    "status",
    "closing_odds",
]

VALID_STATUS = ("open", "won", "lost", "void")


@dataclass
class Bet:
    bet_id: str
    date: str
    event: str
    selection: str
    book: str
    odds_taken: float
    p_estimate: float
    stake: float
    ev_pct: float
    status: str = "open"
    closing_odds: float = 0.0  # 0 = not recorded yet

    @property
    def profit(self) -> float:
        if self.status == "won":
            return self.stake * (self.odds_taken - 1.0)
        if self.status == "lost":
            return -self.stake
        return 0.0  # open or void

    @property
    def settled(self) -> bool:
        return self.status in ("won", "lost")

    @property
    def clv(self) -> float:
        """Closing line value as a fraction. +0.03 means you got 3% better odds
        than the closing price."""
        if not self.closing_odds:
            return 0.0
        return self.odds_taken / self.closing_odds - 1.0


class BetLog:
    """A CSV-backed bet history. Plain text on purpose: it should outlive this
    code and be openable in any spreadsheet."""

    def __init__(self, path: str = "bets.csv"):
        self.path = path
        self.bets: list[Bet] = []
        if os.path.exists(path):
            self.load()

    def load(self) -> None:
        with open(self.path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            self.bets = []
            numeric = {f.name for f in fields(Bet) if f.type is float or f.name in
                       ("odds_taken", "p_estimate", "stake", "ev_pct", "closing_odds")}
            for row in reader:
                data = {k: (float(v) if k in numeric and v != "" else v)
                        for k, v in row.items() if k in FIELDNAMES}
                self.bets.append(Bet(**data))

    def save(self) -> None:
        with open(self.path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=FIELDNAMES)
            writer.writeheader()
            for bet in self.bets:
                writer.writerow(asdict(bet))

    def add(self, bet: Bet) -> Bet:
        if any(b.bet_id == bet.bet_id for b in self.bets):
            raise ValueError(f"bet_id {bet.bet_id!r} already exists")
        if bet.status not in VALID_STATUS:
            raise ValueError(f"status must be one of {VALID_STATUS}")
        self.bets.append(bet)
        self.save()
        return bet

    def settle(self, bet_id: str, status: str, closing_odds: float = None) -> Bet:
        if status not in VALID_STATUS:
            raise ValueError(f"status must be one of {VALID_STATUS}")
        for bet in self.bets:
            if bet.bet_id == bet_id:
                bet.status = status
                if closing_odds is not None:
                    bet.closing_odds = closing_odds
                self.save()
                return bet
        raise KeyError(f"no bet with id {bet_id!r}")

    def next_id(self) -> str:
        return f"b{len(self.bets) + 1:05d}"


def _t_stat_and_p(values: list[float]) -> tuple[float, float]:
    """One-sided test that the mean of `values` is greater than zero."""
    n = len(values)
    if n < 2:
        return 0.0, 1.0
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    if var <= 0:
        return (float("inf"), 0.0) if mean > 0 else (0.0, 1.0)
    t = mean / math.sqrt(var / n)
    p = 1.0 - NormalDist().cdf(t)  # normal approximation; fine once n is large
    return t, p


def analyse(log: BetLog) -> dict:
    settled = [b for b in log.bets if b.settled]
    with_close = [b for b in log.bets if b.closing_odds > 0]

    stats = {
        "total_bets": len(log.bets),
        "settled": len(settled),
        "open": sum(1 for b in log.bets if b.status == "open"),
        "with_closing_line": len(with_close),
    }

    if settled:
        staked = sum(b.stake for b in settled)
        profit = sum(b.profit for b in settled)
        returns = [b.profit / b.stake for b in settled]  # profit per unit staked
        t, p = _t_stat_and_p(returns)
        stats.update(
            {
                "staked": staked,
                "profit": profit,
                "roi": profit / staked if staked else 0.0,
                "hit_rate": sum(1 for b in settled if b.status == "won") / len(settled),
                "avg_odds": sum(b.odds_taken for b in settled) / len(settled),
                "roi_t_stat": t,
                "roi_p_value": p,
            }
        )

    if with_close:
        clvs = [b.clv for b in with_close]
        t, p = _t_stat_and_p(clvs)
        stats.update(
            {
                "avg_clv": sum(clvs) / len(clvs),
                "beat_close_rate": sum(1 for c in clvs if c > 0) / len(clvs),
                "clv_t_stat": t,
                "clv_p_value": p,
            }
        )

    return stats


def format_report(stats: dict) -> str:
    lines = [
        "=" * 62,
        "  HISTORIAL DE APUESTAS",
        "=" * 62,
        f"  Apuestas registradas: {stats['total_bets']}"
        f"   (resueltas: {stats['settled']}, abiertas: {stats['open']})",
    ]

    if not stats.get("settled"):
        lines.append("\n  Sin apuestas resueltas todavia.")
        lines.append("=" * 62)
        return "\n".join(lines)

    lines += [
        "",
        "  RESULTADO",
        f"    Total apostado:  {stats['staked']:>12,.2f}",
        f"    Beneficio:       {stats['profit']:>+12,.2f}",
        f"    ROI:             {stats['roi']:>+12.2%}",
        f"    Acierto:         {stats['hit_rate']:>12.1%}"
        f"   (cuota media {stats['avg_odds']:.2f})",
        "",
        "  ¿ES REAL LA VENTAJA?",
        f"    ROI t-stat: {stats['roi_t_stat']:+.2f}   p-valor: {stats['roi_p_value']:.4f}",
        f"    -> {_verdict(stats['roi_p_value'], stats['settled'])}",
    ]

    if stats.get("with_closing_line"):
        lines += [
            "",
            f"  CLV  (sobre {stats['with_closing_line']} apuestas con cierre registrado)",
            f"    CLV medio:        {stats['avg_clv']:>+10.2%}",
            f"    Bates el cierre:  {stats['beat_close_rate']:>10.1%}",
            f"    CLV t-stat: {stats['clv_t_stat']:+.2f}   p-valor: {stats['clv_p_value']:.4f}",
            f"    -> {_clv_verdict(stats['clv_p_value'], stats['avg_clv'])}",
        ]
    else:
        lines += [
            "",
            "  CLV: sin datos. Registra la cuota de cierre al liquidar cada apuesta:",
            "       es la senal mas rapida de que estas apostando bien.",
        ]

    lines.append("=" * 62)
    return "\n".join(lines)


def _verdict(p_value: float, n: int) -> str:
    if n < 100:
        return f"muestra demasiado pequena ({n}); esto todavia no significa nada"
    if p_value < 0.05:
        return "ventaja estadisticamente significativa por beneficio"
    return "compatible con azar: sigue registrando, no subas las apuestas"


def _clv_verdict(p_value: float, avg_clv: float) -> str:
    if p_value < 0.05 and avg_clv > 0:
        return "bates el cierre de forma consistente: senal solida de ventaja real"
    if avg_clv > 0:
        return "CLV positivo pero aun no concluyente; sigue registrando"
    return "CLV negativo: estas pagando peor que el mercado, revisa el metodo"


def main():
    parser = argparse.ArgumentParser(description="Registro y validacion de apuestas")
    parser.add_argument("--file", default="bets.csv")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="registrar una apuesta")
    add.add_argument("--event", required=True)
    add.add_argument("--selection", required=True)
    add.add_argument("--book", required=True)
    add.add_argument("--odds", type=float, required=True)
    add.add_argument("--p", type=float, required=True, help="tu probabilidad estimada")
    add.add_argument("--stake", type=float, required=True)
    add.add_argument("--date", default=str(date.today()))

    settle = sub.add_parser("settle", help="liquidar una apuesta")
    settle.add_argument("bet_id")
    settle.add_argument("result", choices=["won", "lost", "void"])
    settle.add_argument("--closing-odds", type=float, default=None)

    sub.add_parser("report", help="ver el analisis del historial")

    args = parser.parse_args()
    log = BetLog(args.file)

    if args.command == "add":
        ev = args.p * args.odds - 1.0
        bet = log.add(
            Bet(
                bet_id=log.next_id(),
                date=args.date,
                event=args.event,
                selection=args.selection,
                book=args.book,
                odds_taken=args.odds,
                p_estimate=args.p,
                stake=args.stake,
                ev_pct=ev,
            )
        )
        print(f"Registrada {bet.bet_id}: {bet.selection} @ {bet.odds_taken} ({bet.book})")
        print(f"  EV esperado: {ev:+.2%}")
        if ev <= 0:
            print("  AVISO: esta apuesta tiene EV negativo segun tu propia estimacion.")

    elif args.command == "settle":
        bet = log.settle(args.bet_id, args.result, args.closing_odds)
        print(f"{bet.bet_id} -> {bet.status}   beneficio: {bet.profit:+.2f}")
        if bet.closing_odds:
            print(f"  CLV: {bet.clv:+.2%} (tomaste {bet.odds_taken}, cerro en {bet.closing_odds})")

    elif args.command == "report":
        print(format_report(analyse(log)))


if __name__ == "__main__":
    main()
