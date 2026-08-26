"""Is a backtest's edge real, or did the strategy just get lucky on the data
it was tested on?

The trading equivalent of the CLV problem in apuestas/tracker.py is overfitting:
try enough (fast, slow) pairs on one price history and something will look
great by pure chance, the same way one of 37 roulette numbers will look "hot"
if you watch long enough. The fix is the same kind of discipline as CLV --
check the result against data it never touched -- rather than a better metric.

This module runs the strategy exactly as backtest.py would, then reports the
two questions that matter before anyone should trade a rule for real money:

1. In-sample vs out-of-sample: does the edge survive on the second half of the
   history if you only look at the first half's stats? A rule tuned to fit the
   first half often has nothing left in the second -- that gap alone is the
   most common false-positive detector in retail strategy testing.
2. Statistical significance: are the daily returns distinguishable from noise
   at all (t-stat / p-value), and does the strategy beat a plain buy-and-hold
   of the same asset after the same costs?
"""

import math
from dataclasses import dataclass
from statistics import NormalDist

from .backtest import backtest


def _t_stat_and_p(values: list[float]) -> tuple[float, float]:
    n = len(values)
    if n < 2:
        return 0.0, 1.0
    mean = sum(values) / n
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    if var <= 0:
        return (float("inf"), 0.0) if mean > 0 else (0.0, 1.0)
    t = mean / math.sqrt(var / n)
    p = 1.0 - NormalDist().cdf(t)
    return t, p


def _sharpe(returns: list[float], periods_per_year: int = 252) -> float:
    n = len(returns)
    if n < 2:
        return 0.0
    mean = sum(returns) / n
    var = sum((r - mean) ** 2 for r in returns) / (n - 1)
    sd = math.sqrt(var)
    if sd == 0:
        return 0.0
    return (mean / sd) * math.sqrt(periods_per_year)


@dataclass
class ValidationReport:
    symbol: str
    strategy_name: str
    full_return: float
    full_sharpe: float
    in_sample_return: float
    out_sample_return: float
    out_sample_sharpe: float
    out_sample_t_stat: float
    out_sample_p_value: float
    buy_hold_out_sample_return: float
    beats_buy_hold_out_sample: bool
    trades: int
    max_drawdown: float


def validate(
    symbol: str,
    strategy_name: str,
    closes: list[float],
    signal_fn,
    dates: list[str] = None,
    cost_bps: float = 5.0,
    split: float = 0.5,
) -> ValidationReport:
    """Backtest `signal_fn` on the full history, then again split in half, and
    report whether whatever edge shows up in the first half survives in the
    second -- the part of the process that is easy to skip and that is where
    most home-made strategies quietly fail.
    """
    full_signals = signal_fn(closes)
    full = backtest(closes, full_signals, dates, cost_bps)

    split_idx = int(len(closes) * split)
    in_closes, out_closes = closes[:split_idx], closes[split_idx:]
    out_dates = dates[split_idx:] if dates else None

    in_signals = signal_fn(in_closes)
    in_sample = backtest(in_closes, in_signals, dates[:split_idx] if dates else None, cost_bps)

    out_signals = signal_fn(out_closes)
    out_sample = backtest(out_closes, out_signals, out_dates, cost_bps)

    buy_hold_out = backtest(out_closes, [1] * len(out_closes), out_dates, cost_bps)

    t, p = _t_stat_and_p(out_sample.daily_returns)

    return ValidationReport(
        symbol=symbol,
        strategy_name=strategy_name,
        full_return=full.total_return,
        full_sharpe=_sharpe(full.daily_returns),
        in_sample_return=in_sample.total_return,
        out_sample_return=out_sample.total_return,
        out_sample_sharpe=_sharpe(out_sample.daily_returns),
        out_sample_t_stat=t,
        out_sample_p_value=p,
        buy_hold_out_sample_return=buy_hold_out.total_return,
        beats_buy_hold_out_sample=out_sample.total_return > buy_hold_out.total_return,
        trades=full.trades,
        max_drawdown=full.max_drawdown,
    )


def format_report(r: ValidationReport) -> str:
    lines = [
        "=" * 64,
        f"  {r.strategy_name}  --  {r.symbol}",
        "=" * 64,
        f"  Historial completo:  retorno {r.full_return:+.1%}"
        f"   Sharpe {r.full_sharpe:+.2f}   {r.trades} operaciones"
        f"   drawdown max {r.max_drawdown:.1%}",
        "",
        f"  Primera mitad  (in-sample):   retorno {r.in_sample_return:+.1%}",
        f"  Segunda mitad  (out-of-sample): retorno {r.out_sample_return:+.1%}"
        f"   Sharpe {r.out_sample_sharpe:+.2f}",
        f"  Comprar-y-mantener en la 2a mitad: {r.buy_hold_out_sample_return:+.1%}",
        "",
        f"  t-stat (2a mitad): {r.out_sample_t_stat:+.2f}   p-valor: {r.out_sample_p_value:.3f}",
    ]

    if r.in_sample_return > 0.05 and r.out_sample_return <= 0:
        lines.append("  -> ALERTA: funcionaba en la 1a mitad y se cae en la 2a."
                      " Sintoma clasico de sobreajuste (curve-fitting), no de ventaja real.")
    elif r.out_sample_p_value < 0.05 and r.beats_buy_hold_out_sample:
        lines.append("  -> Supera a comprar-y-mantener con significancia estadistica"
                      " en datos que la estrategia no vio al ajustarse.")
    elif not r.beats_buy_hold_out_sample:
        lines.append("  -> No supera a simplemente comprar y mantener, una vez"
                      " descontados los costes. No vale la pena operarla.")
    else:
        lines.append("  -> Hay una ligera ventaja pero no es estadisticamente"
                      " distinguible del azar todavia.")

    lines.append("=" * 64)
    return "\n".join(lines)


def main():
    import argparse

    from .data import fetch_daily
    from .strategies import rsi_mean_reversion, sma_crossover

    parser = argparse.ArgumentParser(description="Validar una estrategia tecnica con datos reales")
    parser.add_argument("symbol")
    parser.add_argument(
        "strategy",
        choices=["sma", "rsi", "buy_hold", "SMA 20/50", "RSI 14"],
        nargs="?",
        default="sma",
    )
    parser.add_argument("--range", default="5y")
    parser.add_argument("--fast", type=int, default=20)
    parser.add_argument("--slow", type=int, default=50)
    parser.add_argument("--rsi-period", type=int, default=14)
    parser.add_argument("--cost-bps", type=float, default=5.0)
    args = parser.parse_args()

    series = fetch_daily(args.symbol, range_=args.range)

    if args.strategy in ("sma", "SMA 20/50"):
        name = f"SMA {args.fast}/{args.slow}"
        signal_fn = lambda c: sma_crossover(c, args.fast, args.slow)
    elif args.strategy in ("rsi", "RSI 14"):
        name = f"RSI {args.rsi_period}"
        signal_fn = lambda c: rsi_mean_reversion(c, args.rsi_period)
    else:
        from .strategies import buy_and_hold

        name = "Buy & Hold"
        signal_fn = buy_and_hold

    report = validate(args.symbol, name, series.closes, signal_fn, series.dates, args.cost_bps)
    print(format_report(report))


if __name__ == "__main__":
    main()
