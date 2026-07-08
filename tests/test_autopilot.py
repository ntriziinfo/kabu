from __future__ import annotations

import unittest

from daytrade_bot.autopilot import build_monitor_args, build_parser, preflight_block_reason


class AutopilotTest(unittest.TestCase):
    def test_defaults_to_demo_and_requires_explicit_paper_confirmation(self) -> None:
        args = build_parser().parse_args([])
        command = build_monitor_args(args)

        self.assertIn("--demo", command)
        self.assertIn("--paper-execute", command)
        self.assertNotIn("--paper-confirmed", command)
        self.assertNotIn("--paper-no-confirmation-required", command)

    def test_confirmation_flag_is_forwarded_to_monitor(self) -> None:
        args = build_parser().parse_args(["--confirm-paper-orders"])
        command = build_monitor_args(args)

        self.assertIn("--paper-confirmed", command)

    def test_custom_paper_state_files_are_forwarded_to_monitor(self) -> None:
        args = build_parser().parse_args(
            [
                "--paper-positions",
                "data/market_paper_positions.csv",
                "--paper-orders",
                "data/market_paper_orders.csv",
                "--paper-state",
                "data/market_paper_state.json",
            ]
        )
        command = build_monitor_args(args)
        normalized = [item.replace("\\", "/") for item in command]

        self.assertIn("data/market_paper_positions.csv", normalized)
        self.assertIn("data/market_paper_orders.csv", normalized)
        self.assertIn("data/market_paper_state.json", normalized)

    def test_live_mode_omits_demo_timestamp(self) -> None:
        args = build_parser().parse_args(["--live"])
        command = build_monitor_args(args)

        self.assertNotIn("--demo", command)
        self.assertNotIn("--fetched-at", command)

    def test_market_open_guard_can_be_enabled_for_live_test(self) -> None:
        args = build_parser().parse_args(["--live", "--require-market-open"])

        self.assertFalse(args.demo)
        self.assertTrue(args.require_market_open)

    def test_previous_health_error_does_not_block_retry(self) -> None:
        preflight = {"status": "error", "missing_required": [], "health": {"status": "error"}}

        self.assertEqual(preflight_block_reason(preflight), "")


if __name__ == "__main__":
    unittest.main()
