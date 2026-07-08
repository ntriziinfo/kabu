from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def build_health_report(
    failures_path: Path,
    trade_plan_path: Path,
    monitor_status_path: Path,
    paper_state_path: Path,
    prices_path: Path,
) -> dict[str, object]:
    failures = read_csv(failures_path)
    trade_plan = read_csv(trade_plan_path)
    monitor_status = read_json(monitor_status_path)
    paper_state = read_json(paper_state_path)
    prices = read_csv(prices_path)

    warnings: list[dict[str, str]] = []
    blocked = [row for row in trade_plan if row.get("status") == "blocked"]
    ready = [row for row in trade_plan if row.get("status") == "ready"]
    missing_prices = [row for row in trade_plan if row.get("block_reason") == "missing_price"]

    if failures:
        warnings.append({"level": "warn", "message": f"取得失敗 {len(failures)}件"})
    if missing_prices:
        warnings.append({"level": "warn", "message": f"株価不足 {len(missing_prices)}件"})
    if blocked and not ready:
        warnings.append({"level": "info", "message": "発注候補なし"})
    if str(paper_state.get("last_message", "")).endswith("確認待ち"):
        warnings.append({"level": "warn", "message": "紙注文の確認待ち"})
    if monitor_status.get("running") is False and "エラー" in str(monitor_status.get("message", "")):
        warnings.append({"level": "error", "message": str(monitor_status.get("message", ""))})
    if not prices:
        warnings.append({"level": "warn", "message": "株価データなし"})

    status = "ok"
    if any(row["level"] == "error" for row in warnings):
        status = "error"
    elif any(row["level"] == "warn" for row in warnings):
        status = "warn"

    return {
        "status": status,
        "warnings": warnings,
        "failure_count": len(failures),
        "blocked_count": len(blocked),
        "ready_count": len(ready),
        "missing_price_count": len(missing_prices),
        "price_count": len(prices),
        "monitor_message": str(monitor_status.get("message", "")),
        "paper_message": str(paper_state.get("last_message", "")),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize paper trading system health")
    parser.add_argument("--failures", type=Path, default=DATA_DIR / "scan_failures.csv")
    parser.add_argument("--trade-plan", type=Path, default=DATA_DIR / "trade_plan.csv")
    parser.add_argument("--monitor-status", type=Path, default=DATA_DIR / "monitor_status.json")
    parser.add_argument("--paper-state", type=Path, default=DATA_DIR / "paper_state.json")
    parser.add_argument("--prices", type=Path, default=DATA_DIR / "runtime_prices.csv")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    report = build_health_report(
        args.failures,
        args.trade_plan,
        args.monitor_status,
        args.paper_state,
        args.prices,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
