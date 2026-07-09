from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from .doctor import build_doctor_report
from .health import build_health_report
from .market_calendar import market_status, parse_datetime
from .paper_summary import build_paper_summary


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
PRICE_FILE = DATA_DIR / "runtime_prices.csv"
DEMO_PRICE_FILE = DATA_DIR / "latest_prices.csv"
REPORT_PATH = DATA_DIR / "autopilot_report.json"


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def build_monitor_args(args: argparse.Namespace) -> list[str]:
    monitor_args = [
        sys.executable,
        "-m",
        "daytrade_bot.monitor",
        "--symbols",
        str(args.symbols),
        "--once",
        "--interval",
        "1",
        "--evidence-output",
        str(args.evidence_output),
        "--candidates-output",
        str(args.candidates_output),
        "--failures-output",
        str(args.failures_output),
        "--prices",
        str(args.prices),
        "--demo-prices",
        str(args.demo_prices),
        "--trade-plan-output",
        str(args.trade_plan),
        "--paper-positions",
        str(args.paper_positions),
        "--paper-orders",
        str(args.paper_orders),
        "--paper-state",
        str(args.paper_state),
        "--update-prices",
        "--paper-execute",
        "--min-score",
        str(args.min_score),
        "--max-notional",
        str(args.max_notional),
        "--lot-size",
        str(args.lot_size),
        "--stop-loss-pct",
        str(args.stop_loss_pct),
        "--take-profit-pct",
        str(args.take_profit_pct),
        "--max-daily-loss",
        str(args.max_daily_loss),
        "--max-trades-per-day",
        str(args.max_trades_per_day),
        "--max-losing-streak",
        str(args.max_losing_streak),
    ]
    if not args.demo:
        monitor_args.append("--require-realtime-prices")
    if args.demo:
        monitor_args.extend(["--demo", "--fetched-at", args.fetched_at])
    if args.confirm_paper_orders:
        monitor_args.append("--paper-confirmed")
    if args.no_confirmation_required:
        monitor_args.append("--paper-no-confirmation-required")
    return monitor_args


def run_monitor_once(args: argparse.Namespace) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        build_monitor_args(args),
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def build_report(args: argparse.Namespace, result: subprocess.CompletedProcess[str]) -> dict[str, object]:
    price_path = args.prices if args.prices.exists() else args.demo_prices
    market = market_status(parse_datetime(args.as_of))
    health = build_health_report(
        args.failures_output,
        args.trade_plan,
        DATA_DIR / "monitor_status.json",
        args.paper_state,
        price_path,
    )
    summary = build_paper_summary(
        args.paper_positions,
        args.paper_orders,
        price_path,
        args.paper_state,
    )
    status = "ok" if result.returncode == 0 and health["status"] != "error" else "error"
    return {
        "status": status,
        "mode": "demo" if args.demo else "live",
        "ran_at": datetime.now().isoformat(timespec="seconds"),
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "market": market,
        "counts": {
            "evidence": count_csv_rows(args.evidence_output),
            "candidates": count_csv_rows(args.candidates_output),
            "failures": count_csv_rows(args.failures_output),
            "prices": count_csv_rows(price_path),
            "trade_plan": count_csv_rows(args.trade_plan),
            "paper_positions": count_csv_rows(args.paper_positions),
            "paper_orders": count_csv_rows(args.paper_orders),
        },
        "health": health,
        "paper_summary": summary,
    }


def write_report(path: Path, report: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


def market_guard_report(args: argparse.Namespace, market: dict[str, object], reason: str) -> dict[str, object]:
    return {
        "status": "blocked",
        "mode": "demo" if args.demo else "live",
        "ran_at": datetime.now().isoformat(timespec="seconds"),
        "message": reason,
        "market": market,
        "counts": {},
    }


def preflight_block_reason(preflight: dict[str, object]) -> str:
    missing_required = preflight.get("missing_required", [])
    if missing_required:
        return "必須ファイルが不足しているため停止しました"
    return ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run one safe paper-trading autopilot cycle")
    parser.add_argument("--symbols", type=Path, default=DATA_DIR / "symbols.csv")
    parser.add_argument("--evidence-output", type=Path, default=DATA_DIR / "scan_evidence.csv")
    parser.add_argument("--candidates-output", type=Path, default=DATA_DIR / "candidates.csv")
    parser.add_argument("--failures-output", type=Path, default=DATA_DIR / "scan_failures.csv")
    parser.add_argument("--prices", type=Path, default=PRICE_FILE)
    parser.add_argument("--demo-prices", type=Path, default=DEMO_PRICE_FILE)
    parser.add_argument("--trade-plan", type=Path, default=DATA_DIR / "trade_plan.csv")
    parser.add_argument("--paper-positions", type=Path, default=DATA_DIR / "paper_positions.csv")
    parser.add_argument("--paper-orders", type=Path, default=DATA_DIR / "paper_orders.csv")
    parser.add_argument("--paper-state", type=Path, default=DATA_DIR / "paper_state.json")
    parser.add_argument("--report", type=Path, default=REPORT_PATH)
    parser.add_argument("--demo", dest="demo", action="store_true", default=True)
    parser.add_argument("--live", dest="demo", action="store_false")
    parser.add_argument("--fetched-at", default="2026-07-08T09:12:00")
    parser.add_argument("--as-of", help="Override current time for market guard tests")
    parser.add_argument("--require-market-day", action="store_true")
    parser.add_argument("--require-market-open", action="store_true")
    parser.add_argument("--confirm-paper-orders", action="store_true")
    parser.add_argument("--no-confirmation-required", action="store_true")
    parser.add_argument("--min-score", type=float, default=2.2)
    parser.add_argument("--max-notional", type=float, default=500000.0)
    parser.add_argument("--lot-size", type=int, default=100)
    parser.add_argument("--stop-loss-pct", type=float, default=0.02)
    parser.add_argument("--take-profit-pct", type=float, default=0.04)
    parser.add_argument("--max-daily-loss", type=float, default=10000.0)
    parser.add_argument("--max-trades-per-day", type=int, default=10)
    parser.add_argument("--max-losing-streak", type=int, default=3)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    preflight = build_doctor_report(DATA_DIR)
    preflight_block = preflight_block_reason(preflight)
    if preflight_block:
        report = {
            "status": "error",
            "mode": "demo" if args.demo else "live",
            "ran_at": datetime.now().isoformat(timespec="seconds"),
            "message": preflight_block,
            "preflight": preflight,
        }
        write_report(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 1

    market = market_status(parse_datetime(args.as_of))
    if (args.require_market_day or args.require_market_open) and not bool(market["is_trading_day"]):
        report = market_guard_report(args, market, "市場営業日ではないため停止しました")
        write_report(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2
    if args.require_market_open and not bool(market["is_open"]):
        report = market_guard_report(args, market, "立会時間外のため停止しました")
        write_report(args.report, report)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 2

    result = run_monitor_once(args)
    report = build_report(args, result)
    report["preflight"] = {
        "status": preflight["status"],
        "missing_required": preflight["missing_required"],
        "netstock": preflight["netstock"],
    }
    write_report(args.report, report)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
