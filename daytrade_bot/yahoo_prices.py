from __future__ import annotations

import argparse
import csv
import json
import re
import time
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
YAHOO_FINANCE_BASE = "https://finance.yahoo.co.jp"
QUOTE_URL = YAHOO_FINANCE_BASE + "/quote/{symbol}.T"
YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}.T?range=1d&interval=1m"


def read_symbols(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def normalize_symbol(symbol: str) -> str:
    return symbol[:-2] if symbol.upper().endswith(".T") else symbol


def fetch_quote_html(symbol: str, timeout: float = 10.0) -> str:
    normalized = normalize_symbol(symbol)
    request = Request(
        QUOTE_URL.format(symbol=normalized),
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def fetch_chart_payload(symbol: str, timeout: float = 10.0) -> dict[str, object]:
    normalized = normalize_symbol(symbol)
    request = Request(
        YAHOO_CHART_URL.format(symbol=normalized),
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Accept-Language": "ja,en-US;q=0.9,en;q=0.8",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="replace"))


def parse_chart_price(payload: dict[str, object]) -> float | None:
    try:
        chart = payload["chart"]
        if not isinstance(chart, dict):
            return None
        result = chart.get("result")
        if not isinstance(result, list) or not result:
            return None
        first = result[0]
        if not isinstance(first, dict):
            return None
        meta = first.get("meta")
        if not isinstance(meta, dict):
            return None
        price = meta.get("regularMarketPrice")
        if isinstance(price, (int, float)) and price > 0:
            return float(price)
    except (KeyError, TypeError, ValueError):
        return None
    return None


def parse_price(html: str) -> float | None:
    patterns = [
        r'"regularMarketPrice"\s*:\s*\{\s*"raw"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
        r'"currentPrice"\s*:\s*"([0-9,]+(?:\.[0-9]+)?)"',
        r'現在値[^0-9]*([0-9,]+(?:\.[0-9]+)?)',
        r'class="[^"]*Price[^"]*"[^>]*>\s*([0-9,]+(?:\.[0-9]+)?)',
    ]
    for pattern in patterns:
        match = re.search(pattern, html)
        if match:
            return float(match.group(1).replace(",", ""))
    return None


def fetch_price(symbol: str, timeout: float = 10.0) -> tuple[float | None, str]:
    try:
        chart_price = parse_chart_price(fetch_chart_payload(symbol, timeout=timeout))
        if chart_price is not None:
            return chart_price, "yahoo_chart"
    except Exception:
        pass
    html_price = parse_price(fetch_quote_html(symbol, timeout=timeout))
    if html_price is not None:
        return html_price, "yahoo"
    return None, "yahoo"


def write_prices(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["symbol", "name", "price", "timestamp", "source"])
        writer.writeheader()
        writer.writerows(rows)


def update_prices(
    symbols_path: Path,
    output_path: Path,
    timeout: float,
    delay: float,
    demo: bool = False,
    demo_prices_path: Path | None = None,
) -> list[dict[str, str]]:
    symbols = read_symbols(symbols_path)
    now = datetime.now().isoformat(timespec="seconds")
    rows: list[dict[str, str]] = []
    demo_prices = read_existing_prices(demo_prices_path or output_path) if demo else {}

    for index, symbol_row in enumerate(symbols):
        symbol = normalize_symbol(symbol_row["symbol"])
        price: float | None
        source = "yahoo"
        if demo:
            price = demo_prices.get(symbol)
            source = "demo"
        else:
            price, source = fetch_price(symbol, timeout=timeout)
        if price is not None:
            rows.append(
                {
                    "symbol": symbol,
                    "name": symbol_row.get("name", ""),
                    "price": str(price),
                    "timestamp": now,
                    "source": source,
                }
            )
        if not demo and index < len(symbols) - 1 and delay > 0:
            time.sleep(delay)

    write_prices(output_path, rows)
    return rows


def read_existing_prices(path: Path) -> dict[str, float]:
    prices: dict[str, float] = {}
    if not path.exists():
        return prices
    with path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            try:
                prices[normalize_symbol(row["symbol"])] = float(row["price"])
            except (KeyError, ValueError):
                continue
    return prices


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Update Japanese stock prices from Yahoo Finance")
    parser.add_argument("--symbols", type=Path, default=DATA_DIR / "symbols.csv")
    parser.add_argument("--output", type=Path, default=DATA_DIR / "latest_prices.csv")
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--delay", type=float, default=1.0)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--demo-prices", type=Path)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows = update_prices(
        args.symbols,
        args.output,
        args.timeout,
        args.delay,
        args.demo,
        args.demo_prices,
    )
    print(f"wrote {len(rows)} price rows")


if __name__ == "__main__":
    main()
