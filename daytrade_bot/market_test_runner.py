from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from time import sleep

from .market_calendar import market_status


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
STOP_FILE = ROOT / "STOP_TRADING"
STATUS_PATH = DATA_DIR / "market_runner_status.json"
HISTORY_PATH = DATA_DIR / "market_runner_history.jsonl"


def market_file(name: str) -> Path:
    return DATA_DIR / f"market_{name}"


def build_autopilot_args(args: argparse.Namespace) -> list[str]:
    return [
        sys.executable,
        "-m",
        "daytrade_bot.autopilot",
        "--live",
        "--confirm-paper-orders",
        "--require-market-open",
        "--evidence-output",
        str(args.evidence_output),
        "--candidates-output",
        str(args.candidates_output),
        "--failures-output",
        str(args.failures_output),
        "--prices",
        str(args.prices),
        "--trade-plan",
        str(args.trade_plan),
        "--paper-positions",
        str(args.paper_positions),
        "--paper-orders",
        str(args.paper_orders),
        "--paper-state",
        str(args.paper_state),
        "--report",
        str(args.autopilot_report),
        "--max-notional",
        str(args.max_notional),
        "--max-daily-loss",
        str(args.max_daily_loss),
        "--max-trades-per-day",
        str(args.max_trades_per_day),
        "--max-losing-streak",
        str(args.max_losing_streak),
    ]


def decision_for_market(market: dict[str, object], ran_cycles: int, stop_at_close: bool) -> str:
    if bool(market.get("is_open")):
        return "run"
    if stop_at_close and ran_cycles > 0 and market.get("phase") in {"closed", "holiday"}:
        return "stop"
    return "wait"


def write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def append_history(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(data, ensure_ascii=False) + "\n")


def parse_autopilot_stdout(stdout: str) -> dict[str, object]:
    text = stdout.strip()
    if not text:
        return {}
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {"raw": text}


def run_autopilot_cycle(args: argparse.Namespace) -> dict[str, object]:
    result = subprocess.run(
        build_autopilot_args(args),
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    parsed = parse_autopilot_stdout(result.stdout)
    return {
        "returncode": result.returncode,
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "report": parsed,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run live-data paper tests while JPX cash market is open")
    parser.add_argument("--interval", type=float, default=300.0)
    parser.add_argument("--wait-interval", type=float, default=30.0)
    parser.add_argument("--max-cycles", type=int, default=0)
    parser.add_argument("--stop-at-close", action="store_true", default=True)
    parser.add_argument("--keep-waiting-after-close", dest="stop_at_close", action="store_false")
    parser.add_argument("--stop-on-error", action="store_true", default=True)
    parser.add_argument("--keep-running-on-error", dest="stop_on_error", action="store_false")
    parser.add_argument("--status", type=Path, default=STATUS_PATH)
    parser.add_argument("--history", type=Path, default=HISTORY_PATH)
    parser.add_argument("--evidence-output", type=Path, default=market_file("scan_evidence.csv"))
    parser.add_argument("--candidates-output", type=Path, default=market_file("candidates.csv"))
    parser.add_argument("--failures-output", type=Path, default=market_file("scan_failures.csv"))
    parser.add_argument("--prices", type=Path, default=market_file("runtime_prices.csv"))
    parser.add_argument("--trade-plan", type=Path, default=market_file("trade_plan.csv"))
    parser.add_argument("--paper-positions", type=Path, default=market_file("paper_positions.csv"))
    parser.add_argument("--paper-orders", type=Path, default=market_file("paper_orders.csv"))
    parser.add_argument("--paper-state", type=Path, default=market_file("paper_state.json"))
    parser.add_argument("--autopilot-report", type=Path, default=market_file("autopilot_report.json"))
    parser.add_argument("--max-notional", type=float, default=300000.0)
    parser.add_argument("--max-daily-loss", type=float, default=5000.0)
    parser.add_argument("--max-trades-per-day", type=int, default=3)
    parser.add_argument("--max-losing-streak", type=int, default=2)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    ran_cycles = 0
    last_returncode = 0
    write_json(
        args.status,
        {
            "running": True,
            "mode": "live-paper-session",
            "started_at": datetime.now().isoformat(timespec="seconds"),
            "cycles": ran_cycles,
            "message": "waiting_for_market",
        },
    )

    while True:
        market = market_status()
        if STOP_FILE.exists():
            write_json(
                args.status,
                {
                    "running": False,
                    "cycles": ran_cycles,
                    "market": market,
                    "message": "stop_file_detected",
                    "stopped_at": datetime.now().isoformat(timespec="seconds"),
                },
            )
            return last_returncode

        decision = decision_for_market(market, ran_cycles, args.stop_at_close)
        if decision == "wait":
            write_json(
                args.status,
                {
                    "running": True,
                    "cycles": ran_cycles,
                    "market": market,
                    "message": "waiting_for_market",
                    "updated_at": datetime.now().isoformat(timespec="seconds"),
                },
            )
            sleep(max(1.0, args.wait_interval))
            continue
        if decision == "stop":
            write_json(
                args.status,
                {
                    "running": False,
                    "cycles": ran_cycles,
                    "market": market,
                    "message": "market_closed_after_test",
                    "stopped_at": datetime.now().isoformat(timespec="seconds"),
                },
            )
            return last_returncode

        cycle = run_autopilot_cycle(args)
        ran_cycles += 1
        last_returncode = int(cycle["returncode"])
        event = {
            "cycle": ran_cycles,
            "ran_at": datetime.now().isoformat(timespec="seconds"),
            "market": market,
            **cycle,
        }
        append_history(args.history, event)
        write_json(
            args.status,
            {
                "running": True,
                "cycles": ran_cycles,
                "market": market,
                "last_cycle": event,
                "message": "cycle_completed",
                "updated_at": datetime.now().isoformat(timespec="seconds"),
            },
        )

        if last_returncode != 0 and args.stop_on_error:
            write_json(
                args.status,
                {
                    "running": False,
                    "cycles": ran_cycles,
                    "market": market,
                    "last_cycle": event,
                    "message": "stopped_on_error",
                    "stopped_at": datetime.now().isoformat(timespec="seconds"),
                },
            )
            return last_returncode
        if args.max_cycles and ran_cycles >= args.max_cycles:
            write_json(
                args.status,
                {
                    "running": False,
                    "cycles": ran_cycles,
                    "market": market,
                    "last_cycle": event,
                    "message": "max_cycles_reached",
                    "stopped_at": datetime.now().isoformat(timespec="seconds"),
                },
            )
            return last_returncode
        sleep(max(1.0, args.interval))


if __name__ == "__main__":
    sys.exit(main())
