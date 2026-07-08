from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .health import build_health_report
from .market_calendar import market_status
from .netstock_highspeed import get_status
from .paper_summary import build_paper_summary


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def line_count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open("r", encoding="utf-8") as handle:
        return max(0, sum(1 for _ in handle) - 1)


def file_check(path: Path) -> dict[str, object]:
    return {
        "path": str(path),
        "exists": path.exists(),
        "rows": line_count(path) if path.suffix == ".csv" else None,
    }


def build_doctor_report(data_dir: Path = DATA_DIR) -> dict[str, object]:
    netstock = get_status()
    price_path = data_dir / "runtime_prices.csv"
    if not price_path.exists():
        price_path = data_dir / "latest_prices.csv"

    files = {
        "symbols": file_check(data_dir / "symbols.csv"),
        "prices": file_check(price_path),
        "candidates": file_check(data_dir / "candidates.csv"),
        "trade_plan": file_check(data_dir / "trade_plan.csv"),
        "paper_positions": file_check(data_dir / "paper_positions.csv"),
        "paper_orders": file_check(data_dir / "paper_orders.csv"),
        "scan_failures": file_check(data_dir / "scan_failures.csv"),
    }
    health = build_health_report(
        data_dir / "scan_failures.csv",
        data_dir / "trade_plan.csv",
        data_dir / "monitor_status.json",
        data_dir / "paper_state.json",
        price_path,
    )
    paper_summary = build_paper_summary(
        data_dir / "paper_positions.csv",
        data_dir / "paper_orders.csv",
        price_path,
        data_dir / "paper_state.json",
    )
    missing_required = [
        name for name in ("symbols", "prices")
        if not bool(files[name]["exists"])
    ]
    status = "ok" if not missing_required and health["status"] != "error" else "error"

    return {
        "status": status,
        "missing_required": missing_required,
        "netstock": {
            "exe_exists": netstock.exe_exists,
            "shortcut_exists": netstock.shortcut_exists,
            "is_running": netstock.is_running,
            "exe_path": str(netstock.exe_path),
        },
        "market": market_status(),
        "files": files,
        "health": health,
        "paper_summary": paper_summary,
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local diagnostics for the paper trading system")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = build_doctor_report(args.data_dir)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    sys.exit(main())
