from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from time import sleep

from .health import build_health_report
from .market_calendar import market_status, parse_datetime
from .paper_summary import build_paper_summary
from .scanner import read_symbols, scan_symbol, write_candidates, write_evidence, write_failures
from .trade_plan import build_trade_plan
from .yahoo_prices import update_prices


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def build_report(
    args: argparse.Namespace,
    market: dict[str, object],
    failures: list[dict[str, str]],
    errors: list[dict[str, str]],
) -> dict[str, object]:
    health = build_health_report(
        args.failures_output,
        args.trade_plan,
        DATA_DIR / "market_runner_status.json",
        args.paper_state,
        args.prices,
    )
    summary = build_paper_summary(args.paper_positions, args.paper_orders, args.prices, args.paper_state)
    return {
        "status": "ok" if not failures and not errors and health["status"] != "error" else "warn",
        "mode": "preopen_prepare",
        "ran_at": datetime.now().isoformat(timespec="seconds"),
        "paper_execution": False,
        "market": market,
        "errors": errors,
        "counts": {
            "evidence": count_csv_rows(args.evidence_output),
            "candidates": count_csv_rows(args.candidates_output),
            "failures": count_csv_rows(args.failures_output),
            "prices": count_csv_rows(args.prices),
            "trade_plan": count_csv_rows(args.trade_plan),
            "paper_positions": count_csv_rows(args.paper_positions),
            "paper_orders": count_csv_rows(args.paper_orders),
        },
        "health": health,
        "paper_summary": summary,
    }


def run_prepare(args: argparse.Namespace) -> dict[str, object]:
    fetched_at = parse_datetime(args.as_of)
    market = market_status(fetched_at)
    if args.require_market_day and not bool(market["is_trading_day"]):
        return {
            "status": "blocked",
            "mode": "preopen_prepare",
            "ran_at": datetime.now().isoformat(timespec="seconds"),
            "message": "not_trading_day",
            "market": market,
            "paper_execution": False,
            "counts": {},
        }

    symbols = read_symbols(args.symbols)
    all_items = []
    seen_items: set[tuple[str, str, str]] = set()
    failures: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []
    for index, symbol_row in enumerate(symbols):
        symbol = symbol_row["symbol"]
        try:
            items = scan_symbol(symbol, fetched_at, args.demo, args.max_items, args.retries, args.timeout)
            for item in items:
                key = (item.symbol, item.title, item.url)
                if key not in seen_items:
                    seen_items.add(key)
                    all_items.append(item)
        except Exception as exc:
            failures.append(
                {
                    "timestamp": fetched_at.isoformat(),
                    "symbol": symbol,
                    "name": symbol_row.get("name", ""),
                    "error": str(exc),
                }
            )
        if not args.demo and index < len(symbols) - 1 and args.delay > 0:
            sleep(args.delay)

    write_evidence(args.evidence_output, all_items)
    write_failures(args.failures_output, failures)
    write_candidates(args.candidates_output, symbols, all_items, fetched_at)
    try:
        update_prices(args.symbols, args.prices, args.timeout, args.delay, demo=args.demo, demo_prices_path=args.demo_prices)
    except Exception as exc:
        errors.append({"stage": "price_update", "error": str(exc)})
    build_trade_plan(
        args.candidates_output,
        args.prices,
        args.trade_plan,
        args.min_score,
        args.max_notional,
        args.lot_size,
        args.stop_loss_pct,
        args.take_profit_pct,
    )
    return build_report(args, market, failures, errors)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prepare live-data market paper test files before the open")
    parser.add_argument("--symbols", type=Path, default=DATA_DIR / "symbols.csv")
    parser.add_argument("--evidence-output", type=Path, default=DATA_DIR / "market_scan_evidence.csv")
    parser.add_argument("--candidates-output", type=Path, default=DATA_DIR / "market_candidates.csv")
    parser.add_argument("--failures-output", type=Path, default=DATA_DIR / "market_scan_failures.csv")
    parser.add_argument("--prices", type=Path, default=DATA_DIR / "market_runtime_prices.csv")
    parser.add_argument("--demo-prices", type=Path, default=DATA_DIR / "latest_prices.csv")
    parser.add_argument("--trade-plan", type=Path, default=DATA_DIR / "market_trade_plan.csv")
    parser.add_argument("--paper-positions", type=Path, default=DATA_DIR / "market_paper_positions.csv")
    parser.add_argument("--paper-orders", type=Path, default=DATA_DIR / "market_paper_orders.csv")
    parser.add_argument("--paper-state", type=Path, default=DATA_DIR / "market_paper_state.json")
    parser.add_argument("--report", type=Path, default=DATA_DIR / "market_preopen_report.json")
    parser.add_argument("--as-of")
    parser.add_argument("--require-market-day", action="store_true", default=True)
    parser.add_argument("--allow-non-market-day", dest="require_market_day", action="store_false")
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--max-items", type=int, default=10)
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--min-score", type=float, default=2.2)
    parser.add_argument("--max-notional", type=float, default=300000.0)
    parser.add_argument("--lot-size", type=int, default=100)
    parser.add_argument("--stop-loss-pct", type=float, default=0.02)
    parser.add_argument("--take-profit-pct", type=float, default=0.04)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = run_prepare(args)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report["status"] != "blocked" else 2


if __name__ == "__main__":
    sys.exit(main())
