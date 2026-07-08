from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from time import sleep

from .scanner import main as scanner_main


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
STATUS_PATH = DATA_DIR / "monitor_status.json"
STOP_FILE = ROOT / "STOP_TRADING"


def write_status(**values: object) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    current = {}
    if STATUS_PATH.exists():
        try:
            current = json.loads(STATUS_PATH.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            current = {}
    current.update(values)
    current["updated_at"] = datetime.now().isoformat(timespec="seconds")
    STATUS_PATH.write_text(json.dumps(current, ensure_ascii=False, indent=2), encoding="utf-8")


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def run_scan_cycle(args: argparse.Namespace) -> None:
    import sys

    scanner_args = [
        "daytrade_bot.scanner",
        "--symbols",
        str(args.symbols),
        "--evidence-output",
        str(args.evidence_output),
        "--candidates-output",
        str(args.candidates_output),
        "--failures-output",
        str(args.failures_output),
        "--max-items",
        str(args.max_items),
        "--delay",
        str(args.delay),
        "--retries",
        str(args.retries),
        "--timeout",
        str(args.timeout),
    ]
    if args.demo:
        scanner_args.append("--demo")
    if args.fetched_at:
        scanner_args.extend(["--fetched-at", args.fetched_at])

    original_argv = sys.argv
    try:
        sys.argv = scanner_args
        scanner_main()
    finally:
        sys.argv = original_argv

    write_status(
        running=True,
        mode="demo" if args.demo else "live",
        last_cycle_at=datetime.now().isoformat(timespec="seconds"),
        candidates=count_csv_rows(args.candidates_output),
        evidence=count_csv_rows(args.evidence_output),
        failures=count_csv_rows(args.failures_output),
        message="scan cycle finished",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run repeated candidate scans")
    parser.add_argument("--symbols", type=Path, default=DATA_DIR / "symbols.csv")
    parser.add_argument("--evidence-output", type=Path, default=DATA_DIR / "scan_evidence.csv")
    parser.add_argument("--candidates-output", type=Path, default=DATA_DIR / "candidates.csv")
    parser.add_argument("--failures-output", type=Path, default=DATA_DIR / "scan_failures.csv")
    parser.add_argument("--max-items", type=int, default=10)
    parser.add_argument("--delay", type=float, default=1.5)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--timeout", type=float, default=10.0)
    parser.add_argument("--interval", type=float, default=60.0)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--fetched-at")
    parser.add_argument("--once", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    write_status(running=True, mode="demo" if args.demo else "live", message="monitor started")

    try:
        while True:
            if STOP_FILE.exists():
                write_status(running=False, message="stopped by STOP_TRADING")
                break
            run_scan_cycle(args)
            if args.once:
                write_status(running=False, message="one-shot monitor finished")
                break
            sleep(max(1.0, args.interval))
    except KeyboardInterrupt:
        write_status(running=False, message="monitor interrupted")
        raise
    except Exception as exc:
        write_status(running=False, message=f"monitor error: {exc}")
        raise


if __name__ == "__main__":
    main()

