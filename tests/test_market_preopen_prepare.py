from __future__ import annotations

import unittest

from daytrade_bot.market_preopen_prepare import build_parser, build_report, count_csv_rows


class MarketPreopenPrepareTest(unittest.TestCase):
    def test_defaults_write_market_files_and_do_not_execute_paper(self) -> None:
        args = build_parser().parse_args([])

        self.assertIn("market_scan_evidence.csv", str(args.evidence_output))
        self.assertIn("market_runtime_prices.csv", str(args.prices))
        self.assertIn("market_trade_plan.csv", str(args.trade_plan))
        self.assertTrue(args.require_market_day)

    def test_missing_csv_counts_as_zero(self) -> None:
        self.assertEqual(count_csv_rows(__import__("pathlib").Path("does-not-exist.csv")), 0)

    def test_report_warns_when_stage_errors_exist(self) -> None:
        args = build_parser().parse_args([])
        report = build_report(
            args,
            {"is_trading_day": True, "is_open": False},
            failures=[],
            errors=[{"stage": "price_update", "error": "network"}],
        )

        self.assertEqual(report["status"], "warn")
        self.assertEqual(report["errors"][0]["stage"], "price_update")


if __name__ == "__main__":
    unittest.main()
