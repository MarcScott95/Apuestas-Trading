"""Value detection: turn a set of real bookmaker prices into a fair probability,
then find the bets where the price on offer beats it.

The workflow this implements is the practical version of "EV > 0 requires
p_true > 1/odds":

  1. Take a market (one event, all its outcomes) priced by several bookmakers.
  2. Strip the margin (the *vig*) to recover the probabilities a book is really
     working with. A market priced 1.91/1.91 implies 52.36% + 52.36% = 104.71%;
     that extra 4.71% is the commission, and it must be removed before any of
     the numbers mean anything.
  3. Decide a fair probability, either from your own estimate or from the
     consensus of the sharpest books available.
  4. Take the BEST price on offer across all books and check it against that
     probability.

Step 4 matters more than people expect. Always taking the best available price
instead of an average one is worth roughly 1-2% on its own, which is the size
of a respectable edge before you have modelled anything at all.
"""

import argparse
import json
from dataclasses import dataclass

from .edge import implied_probability
from .kelly import kelly_fraction

DEVIG_METHODS = ("multiplicative", "additive", "power")


def devig(odds: list[float], method: str = "multiplicative") -> list[float]:
    """Recover fair probabilities from a complete market's prices.

    - multiplicative: scale every implied probability down proportionally.
      Simple, standard, and the right default for two-way markets.
    - additive: subtract the margin equally from each outcome. Treats the
      commission as a flat charge rather than a proportional one.
    - power: raise each implied probability to a power k so they sum to 1.
      Handles favourite-longshot bias better, where books load more margin
      onto the longshot than onto the favourite.

    The choice matters most on lopsided markets: on a 1.10 / 8.00 market the
    three methods can disagree by more than a typical edge, so the method is
    itself an assumption worth stating.
    """
    if len(odds) < 2:
        raise ValueError("a market needs at least two outcomes")
    raw = [implied_probability(o) for o in odds]
    total = sum(raw)

    if total <= 1.0:
        # No margin (or an arbitrage): nothing to strip.
        return raw

    if method == "multiplicative":
        return [r / total for r in raw]

    if method == "additive":
        excess = (total - 1.0) / len(raw)
        adjusted = [max(1e-9, r - excess) for r in raw]
        scale = sum(adjusted)
        return [a / scale for a in adjusted]

    if method == "power":
        lo, hi = 1.0, 100.0
        for _ in range(200):
            k = (lo + hi) / 2
            if sum(r**k for r in raw) > 1.0:
                lo = k
            else:
                hi = k
        k = (lo + hi) / 2
        out = [r**k for r in raw]
        scale = sum(out)
        return [o / scale for o in out]

    raise ValueError(f"unknown devig method {method!r}; use one of {DEVIG_METHODS}")


@dataclass
class Market:
    """One event, its mutually exclusive outcomes, and every price seen for them."""

    event: str
    selections: list[str]
    prices: dict[str, list[float]]  # bookmaker -> odds, aligned with `selections`

    def __post_init__(self):
        for book, odds in self.prices.items():
            if len(odds) != len(self.selections):
                raise ValueError(
                    f"{book} has {len(odds)} prices for {len(self.selections)} selections"
                )

    def best_price(self, index: int) -> tuple[float, str]:
        """Best available odds for one selection, and which book offers them."""
        book, odds = max(self.prices.items(), key=lambda kv: kv[1][index])
        return odds[index], book

    def margins(self, method: str = "multiplicative") -> dict[str, float]:
        """Each book's overround on this market."""
        return {
            book: sum(implied_probability(o) for o in odds) - 1.0
            for book, odds in self.prices.items()
        }

    def fair_probabilities(
        self, reference_books: list[str] = None, method: str = "multiplicative"
    ) -> list[float]:
        """Consensus fair probabilities, devigged and averaged over the books used.

        Passing `reference_books` restricts the consensus to the books you trust
        (typically the sharpest one available). Their devigged line is usually a
        better probability estimate than anything a casual bettor can model, so
        comparing soft books against it is the most practical way to find value
        without building a model at all.
        """
        books = reference_books or list(self.prices)
        missing = [b for b in books if b not in self.prices]
        if missing:
            raise KeyError(f"no prices for reference book(s): {missing}")

        devigged = [devig(self.prices[b], method) for b in books]
        return [sum(col) / len(col) for col in zip(*devigged)]


@dataclass
class ValueBet:
    event: str
    selection: str
    odds: float
    book: str
    p_fair: float
    ev: float
    kelly: float
    stake: float

    @property
    def fair_odds(self) -> float:
        return 1.0 / self.p_fair


def find_value(
    market: Market,
    estimates: dict[str, float] = None,
    reference_books: list[str] = None,
    method: str = "multiplicative",
    min_ev: float = 0.0,
    bankroll: float = 1000.0,
    kelly_multiple: float = 0.5,
) -> list[ValueBet]:
    """Find every selection whose best available price beats its fair probability.

    `estimates` uses your own probabilities (keyed by selection name);
    omitting it falls back to the devigged consensus of `reference_books`.
    """
    if estimates:
        unknown = set(estimates) - set(market.selections)
        if unknown:
            raise KeyError(f"estimates for unknown selections: {sorted(unknown)}")
        total = sum(estimates.values())
        if not 0.97 <= total <= 1.03:
            raise ValueError(
                f"your probabilities sum to {total:.3f}; a complete market must sum to 1.0"
            )

    consensus = market.fair_probabilities(reference_books, method)

    found = []
    for i, selection in enumerate(market.selections):
        p_fair = estimates.get(selection, consensus[i]) if estimates else consensus[i]
        odds, book = market.best_price(i)

        ev = p_fair * odds - 1.0
        if ev <= min_ev:
            continue

        f = kelly_fraction(p_fair, odds, kelly_multiple)
        found.append(
            ValueBet(
                event=market.event,
                selection=selection,
                odds=odds,
                book=book,
                p_fair=p_fair,
                ev=ev,
                kelly=f,
                stake=round(bankroll * f, 2),
            )
        )

    return sorted(found, key=lambda v: v.ev, reverse=True)


def format_market_report(
    market: Market,
    value_bets: list[ValueBet],
    reference_books: list[str] = None,
    method: str = "multiplicative",
) -> str:
    fair = market.fair_probabilities(reference_books, method)
    margins = market.margins()

    lines = [
        "=" * 72,
        f"  {market.event}",
        "=" * 72,
        "  Comision por casa: "
        + ", ".join(f"{b} {m:+.2%}" for b, m in sorted(margins.items())),
        f"  Referencia: {', '.join(reference_books or list(market.prices))}"
        f"   (devig: {method})",
        "",
        f"  {'Seleccion':<22}{'Justa':>9}{'Cuota justa':>13}{'Mejor':>9}{'Casa':>12}{'EV':>9}",
        "  " + "-" * 70,
    ]

    for i, selection in enumerate(market.selections):
        odds, book = market.best_price(i)
        ev = fair[i] * odds - 1.0
        flag = "  <-- VALOR" if ev > 0 else ""
        lines.append(
            f"  {selection:<22}{fair[i]:>9.2%}{1 / fair[i]:>13.2f}"
            f"{odds:>9.2f}{book:>12}{ev:>+9.2%}{flag}"
        )

    if value_bets:
        lines += ["", "  APUESTAS CON VALOR (medio Kelly):"]
        for v in value_bets:
            lines.append(
                f"    {v.selection} @ {v.odds} en {v.book}"
                f"  |  EV {v.ev:+.2%}  |  apostar {v.kelly:.2%} de banca = {v.stake:,.2f}"
            )
    else:
        lines += ["", "  Sin valor en este mercado. No apostar."]

    lines.append("=" * 72)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Detectar apuestas de valor a partir de cuotas reales"
    )
    parser.add_argument("markets", help="fichero JSON con los mercados")
    parser.add_argument(
        "--reference",
        nargs="*",
        default=None,
        help="casas a usar como referencia justa (idealmente las sharp)",
    )
    parser.add_argument("--method", choices=DEVIG_METHODS, default="multiplicative")
    parser.add_argument("--min-ev", type=float, default=0.0, help="EV minimo, ej. 0.02")
    parser.add_argument("--bankroll", type=float, default=1000.0)
    parser.add_argument("--kelly", type=float, default=0.5)
    args = parser.parse_args()

    total_value = 0
    for market in load_markets(args.markets):
        bets = find_value(
            market,
            reference_books=args.reference,
            method=args.method,
            min_ev=args.min_ev,
            bankroll=args.bankroll,
            kelly_multiple=args.kelly,
        )
        total_value += len(bets)
        print(format_market_report(market, bets, args.reference, args.method))
        print()

    print(f"{total_value} apuesta(s) con valor por encima de EV {args.min_ev:+.2%}")


def load_markets(path: str) -> list[Market]:
    """Read markets from a JSON file.

    [
      {
        "event": "Team A vs Team B",
        "selections": ["A", "B"],
        "prices": {"pinnacle": [1.95, 1.95], "softbook": [2.10, 1.80]}
      }
    ]
    """
    with open(path, encoding="utf-8") as fh:
        raw = json.load(fh)
    return [
        Market(event=m["event"], selections=m["selections"], prices=m["prices"])
        for m in raw
    ]


if __name__ == "__main__":
    main()
