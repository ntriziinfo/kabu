from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from daytrade_bot.market_test_report import build_market_test_report, read_last_jsonl


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class MarketTestReportTest(unittest.TestCase):
    def test_reads_last_jsonl_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "history.jsonl"
            path.write_text('{"cycle": 1}\n{"cycle": 2}\n', encoding="utf-8")

            self.assertEqual(read_last_jsonl(path)["cycle"], 2)

    def test_builds_counts_and_summary_from_market_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_csv(root / "market_runtime_prices.csv", [{"symbol": "7203", "price": "1000"}], ["symbol", "price"])
            write_csv(
                root / "market_trade_plan.csv",
                [{"symbol": "7203", "status": "blocked", "block_reason": "score_below_threshold"}],
                ["symbol", "status", "block_reason"],
            )
            write_csv(root / "market_scan_failures.csv", [], ["timestamp", "symbol", "name", "error"])
            write_csv(root / "market_scan_evidence.csv", [{"symbol": "7203"}], ["symbol"])
            write_csv(root / "market_candidates.csv", [{"symbol": "7203"}], ["symbol"])
            write_csv(root / "market_paper_positions.csv", [], ["symbol", "quantity"])
            write_csv(root / "market_paper_orders.csv", [], ["symbol", "quantity", "realized_pnl"])
            (root / "market_paper_state.json").write_text(json.dumps({"realized_pnl": 0}), encoding="utf-8")

            report = build_market_test_report(root)

            self.assertEqual(report["counts"]["prices"], 1)
            self.assertEqual(report["counts"]["evidence"], 1)
            self.assertEqual(report["paper_summary"]["total_pnl"], 0.0)


if __name__ == "__main__":
    unittest.main()
