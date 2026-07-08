from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path

from .health import build_health_report
from .market_calendar import market_status
from .netstock_highspeed import get_status
from .paper_summary import build_paper_summary


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
STOP_FILE = ROOT / "STOP_TRADING"


def market_path(name: str) -> Path:
    return DATA_DIR / f"market_{name}"


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {"error": "invalid_json", "path": str(path)}


def read_last_jsonl(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    last_line = ""
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                last_line = line
    if not last_line:
        return {}
    try:
        return json.loads(last_line)
    except json.JSONDecodeError:
        return {"error": "invalid_jsonl", "path": str(path)}


def count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8", newline="") as handle:
        return max(0, sum(1 for _ in csv.reader(handle)) - 1)


def file_snapshot(path: Path) -> dict[str, object]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "rows": count_csv_rows(path) if path.suffix == ".csv" else None,
        "updated_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if path.exists() else "",
    }


def build_market_test_report(data_dir: Path = DATA_DIR) -> dict[str, object]:
    paths = {
        "runner_status": data_dir / "market_runner_status.json",
        "runner_history": data_dir / "market_runner_history.jsonl",
        "autopilot_report": data_dir / "market_autopilot_report.json",
        "preopen_report": data_dir / "market_preopen_report.json",
        "evidence": data_dir / "market_scan_evidence.csv",
        "candidates": data_dir / "market_candidates.csv",
        "failures": data_dir / "market_scan_failures.csv",
        "prices": data_dir / "market_runtime_prices.csv",
        "trade_plan": data_dir / "market_trade_plan.csv",
        "paper_positions": data_dir / "market_paper_positions.csv",
        "paper_orders": data_dir / "market_paper_orders.csv",
        "paper_state": data_dir / "market_paper_state.json",
    }
    runner_status = read_json(paths["runner_status"])
    autopilot_report = read_json(paths["autopilot_report"])
    preopen_report = read_json(paths["preopen_report"])
    health = build_health_report(
        paths["failures"],
        paths["trade_plan"],
        paths["runner_status"],
        paths["paper_state"],
        paths["prices"],
    )
    paper_summary = build_paper_summary(
        paths["paper_positions"],
        paths["paper_orders"],
        paths["prices"],
        paths["paper_state"],
    )
    netstock = get_status()
    files = {name: file_snapshot(path) for name, path in paths.items() if path.suffix == ".csv"}
    counts = {name: int(snapshot["rows"] or 0) for name, snapshot in files.items()}
    warnings: list[str] = []
    if STOP_FILE.exists():
        warnings.append("stop_file_exists")
    if not paths["prices"].exists() or counts.get("prices", 0) == 0:
        warnings.append("missing_market_prices")
    if health["status"] == "error":
        warnings.append("health_error")
    elif health["status"] == "warn":
        warnings.append("health_warning")

    status = "ok"
    if "health_error" in warnings:
        status = "error"
    elif warnings:
        status = "warn"

    return {
        "status": status,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "market": market_status(),
        "stop_trading": STOP_FILE.exists(),
        "warnings": warnings,
        "netstock": {
            "exe_exists": netstock.exe_exists,
            "shortcut_exists": netstock.shortcut_exists,
            "is_running": netstock.is_running,
            "exe_path": str(netstock.exe_path),
        },
        "runner_status": runner_status,
        "last_cycle": read_last_jsonl(paths["runner_history"]),
        "last_preopen_report": preopen_report,
        "last_autopilot_report": autopilot_report,
        "counts": counts,
        "files": files,
        "health": health,
        "paper_summary": paper_summary,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize the live-market paper test state")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--output", type=Path, default=DATA_DIR / "market_test_report.json")
    parser.add_argument("--no-output", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = build_market_test_report(args.data_dir)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if not args.no_output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if report["status"] != "error" else 1


if __name__ == "__main__":
    raise SystemExit(main())
