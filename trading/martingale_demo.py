"""Why 'Martingale for trading' (doubling down / grid / DCA-into-losses) is
WORSE than in roulette, not equally bad.

The roulette version fails because of a fixed negative expectation per unit
wagered (see roulette_fibonacci/ev_proof.py). That same failure applies here
too -- staking cannot create edge -- but trading a grid/martingale system adds
two extra ways to lose that roulette does not have:

1. No table maximum. A roulette bet is capped by the table; a leveraged trading
   position is capped only by your account equity and your broker's margin
   call, which arrives without warning.

2. Spins are independent; prices are not. A losing streak in roulette can only
   go on so long before the law of large numbers pulls it back toward 48.65%
   winners. A market TREND has no such guarantee -- price can move against a
   doubled-down position for weeks, because unlike roulette outcomes, today's
   price move and tomorrow's are not drawn independently from a fixed
   distribution. This is exactly the mechanism that has wiped out real retail
   FX/CFD accounts running 'grid' bots: each add-on doubles exposure into a
   trend that has no obligation to reverse before the account is gone.

This module runs a martingale-style doubler against a REAL market decline
(QQQ, peak to trough in 2022, -35.6%) and compares it to simply holding a
fixed position, to make the failure mode concrete rather than asserted.
"""

import argparse
from dataclasses import dataclass

from .data import fetch_daily


@dataclass
class MartingaleResult:
    final_equity: float
    peak_exposure: float
    margin_called: bool
    margin_call_day: int
    equity_curve: list[float]


def simulate_martingale_buyer(
    closes: list[float],
    initial_position: float = 1.0,
    add_on_drop_pct: float = 0.05,
    account_equity: float = 100.0,
    max_leverage: float = 10.0,
) -> MartingaleResult:
    """'Buy the dip, double down every time it drops further' -- a grid /
    martingale position-sizing rule applied to a real price series.

    Every time price falls `add_on_drop_pct` below the last entry, the position
    size doubles (classic martingale progression) on the theory that the next
    bounce will recover everything at once. `max_leverage` times account equity
    is the hard stop a real broker would enforce -- exceeding it is a margin
    call, and the account is forcibly closed out at whatever price triggered it.
    """
    position = initial_position
    entry_price = closes[0]
    total_shares = position / entry_price
    cost_basis = position

    equity_curve = [account_equity]
    peak_exposure = position
    margin_called = False
    margin_call_day = -1

    for i in range(1, len(closes)):
        price = closes[i]
        mark_to_market = total_shares * price
        equity = account_equity - cost_basis + mark_to_market
        equity_curve.append(equity)

        exposure = total_shares * price
        peak_exposure = max(peak_exposure, exposure)

        if exposure > max_leverage * account_equity:
            margin_called = True
            margin_call_day = i
            break

        if price <= entry_price * (1 - add_on_drop_pct):
            add_on = position  # double the CURRENT position size
            total_shares += add_on / price
            cost_basis += add_on
            position += add_on
            entry_price = price

    return MartingaleResult(
        final_equity=equity_curve[-1],
        peak_exposure=peak_exposure,
        margin_called=margin_called,
        margin_call_day=margin_call_day,
        equity_curve=equity_curve,
    )


def simulate_fixed_position(
    closes: list[float], position: float = 1.0, account_equity: float = 100.0
) -> list[float]:
    """The comparison that matters: buy once, don't add to losers, ride it out."""
    shares = position / closes[0]
    return [account_equity - position + shares * price for price in closes]


def main():
    parser = argparse.ArgumentParser(
        description="Martingale/grid position sizing against a real market decline"
    )
    parser.add_argument("--symbol", default="QQQ")
    parser.add_argument("--start", default="2021-11-19")
    parser.add_argument("--end", default="2022-10-13")
    parser.add_argument("--initial-position", type=float, default=10.0, help="units of account equity risked on the first entry")
    parser.add_argument("--add-on-drop", type=float, default=0.05)
    parser.add_argument("--max-leverage", type=float, default=10.0)
    args = parser.parse_args()

    series = fetch_daily(args.symbol, range_="10y")
    idx = [i for i, d in enumerate(series.dates) if args.start <= d <= args.end]
    closes = [series.closes[i] for i in idx]
    dates = [series.dates[i] for i in idx]

    decline = closes[-1] / max(closes) - 1
    print(f"{args.symbol}, {dates[0]} -> {dates[-1]}  ({len(closes)} dias)")
    print(f"Caida maxima real en el periodo: {decline:.1%}\n")

    grid = simulate_martingale_buyer(
        closes,
        initial_position=args.initial_position,
        add_on_drop_pct=args.add_on_drop,
        max_leverage=args.max_leverage,
    )
    flat = simulate_fixed_position(closes, position=args.initial_position)

    print(f"{'Estrategia':<30}{'Capital final':>16}{'Exposicion pico':>18}")
    print("-" * 64)
    print(f"{'Posicion fija (sin doblar)':<30}{flat[-1]:>16.2f}{max(flat):>18.2f}")

    if grid.margin_called:
        print(
            f"{'Martingala / grid':<30}{'LIQUIDADA':>16}{grid.peak_exposure:>18.2f}"
            f"   (dia {grid.margin_call_day}: {dates[grid.margin_call_day]})"
        )
        print(
            f"\nLa cuenta salta por margin call el dia {grid.margin_call_day} "
            f"({dates[grid.margin_call_day]}),\n"
            f"con la exposicion en {grid.peak_exposure:.0f} unidades sobre un capital de 100 "
            f"-- {grid.peak_exposure/100:.1f}x apalancado.\n"
            "El mercado NO tuvo que caer mucho mas para acabar con la cuenta; solo tuvo\n"
            "que seguir la misma tendencia unos dias mas, que es justo lo que las\n"
            "tendencias reales hacen y las tiradas de ruleta nunca hacen."
        )
    else:
        print(f"{'Martingala / grid':<30}{grid.final_equity:>16.2f}{grid.peak_exposure:>18.2f}")
        print(
            f"\nSobrevivio esta vez, pero con {grid.peak_exposure/100:.1f}x de exposicion "
            f"pico sobre el capital.\nUna caida un poco mayor o mas prolongada "
            "la habria liquidado."
        )


if __name__ == "__main__":
    main()
