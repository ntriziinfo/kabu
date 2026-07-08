from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from daytrade_bot.doctor import build_doctor_report


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class DoctorReportTest(unittest.TestCase):
    def test_reports_error_when_required_inputs_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            report = build_doctor_report(Path(temp))

            self.assertEqual(report["status"], "error")
            self.assertEqual(report["missing_required"], ["symbols", "prices"])

    def test_accepts_symbols_and_price_file_as_required_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            write_csv(root / "symbols.csv", [{"symbol": "7203", "name": "Toyota"}], ["symbol", "name"])
            write_csv(root / "latest_prices.csv", [{"symbol": "7203", "price": 3000}], ["symbol", "price"])

            report = build_doctor_report(root)

            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["missing_required"], [])
            self.assertEqual(report["files"]["symbols"]["rows"], 1)
            self.assertEqual(report["files"]["prices"]["rows"], 1)


if __name__ == "__main__":
    unittest.main()
