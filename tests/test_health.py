from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from daytrade_bot.health import build_health_report


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class HealthReportTest(unittest.TestCase):
    def test_warns_for_failures_missing_prices_and_confirmation_wait(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            failures = root / "failures.csv"
            trade_plan = root / "trade_plan.csv"
            monitor_status = root / "monitor_status.json"
            paper_state = root / "paper_state.json"
            prices = root / "prices.csv"

            write_csv(
                failures,
                [{"timestamp": "2026-07-08T09:00:00", "symbol": "7203", "name": "Toyota", "error": "timeout"}],
                ["timestamp", "symbol", "name", "error"],
            )
            write_csv(
                trade_plan,
                [
                    {
                        "symbol": "7203",
                        "status": "blocked",
                        "block_reason": "missing_price",
                    }
                ],
                ["symbol", "status", "block_reason"],
            )
            monitor_status.write_text(json.dumps({"running": False, "message": "stopped"}), encoding="utf-8")
            paper_state.write_text(json.dumps({"last_message": "紙注文の実行前確認待ち"}), encoding="utf-8")
            write_csv(prices, [], ["symbol", "price"])

            report = build_health_report(failures, trade_plan, monitor_status, paper_state, prices)
            messages = [row["message"] for row in report["warnings"]]

            self.assertEqual(report["status"], "warn")
            self.assertIn("取得失敗 1件", messages)
            self.assertIn("株価不足 1件", messages)
            self.assertIn("紙注文の確認待ち", messages)
            self.assertIn("株価データなし", messages)


if __name__ == "__main__":
    unittest.main()
