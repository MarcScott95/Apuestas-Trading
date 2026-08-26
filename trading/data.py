"""Real historical price data, fetched once and cached locally.

Uses Yahoo Finance's public chart endpoint -- no API key, no dependency beyond
the standard library. This is for backtesting and research; it is delayed data,
not a feed to trade live from.
"""

import csv
import json
import os
import urllib.request
from dataclasses import dataclass

CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", ".cache", "prices")


@dataclass
class PriceSeries:
    symbol: str
    dates: list[str]
    closes: list[float]

    def __len__(self):
        return len(self.closes)


def _cache_path(symbol: str, range_: str, interval: str) -> str:
    return os.path.join(CACHE_DIR, f"{symbol}_{range_}_{interval}.csv")


def fetch_daily(
    symbol: str, range_: str = "5y", interval: str = "1d", use_cache: bool = True
) -> PriceSeries:
    """Fetch a daily close-price history for `symbol`.

    `range_` and `interval` follow Yahoo's chart API vocabulary (e.g. "5y" +
    "1d", or "1y" + "1wk"). Results are cached to a local CSV so repeated runs
    (and CI, and tests) don't refetch or depend on network access.
    """
    path = _cache_path(symbol, range_, interval)
    if use_cache and os.path.exists(path):
        return _load_csv(symbol, path)

    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
        f"?range={range_}&interval={interval}"
    )
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        payload = json.load(resp)

    result = payload["chart"]["result"]
    if not result:
        raise ValueError(f"no data returned for {symbol!r}")
    r = result[0]
    timestamps = r["timestamp"]
    closes = r["indicators"]["quote"][0]["close"]

    import datetime

    dates, clean_closes = [], []
    for ts, close in zip(timestamps, closes):
        if close is None:
            continue
        dates.append(datetime.datetime.utcfromtimestamp(ts).strftime("%Y-%m-%d"))
        clean_closes.append(float(close))

    series = PriceSeries(symbol, dates, clean_closes)
    _save_csv(series, path)
    return series


def _save_csv(series: PriceSeries, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["date", "close"])
        writer.writerows(zip(series.dates, series.closes))


def _load_csv(symbol: str, path: str) -> PriceSeries:
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.reader(fh)
        next(reader)
        dates, closes = [], []
        for date, close in reader:
            dates.append(date)
            closes.append(float(close))
    return PriceSeries(symbol, dates, closes)
