from __future__ import annotations

import unittest

from daytrade_bot.autopilot import build_monitor_args, build_parser


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

    def test_live_mode_omits_demo_timestamp(self) -> None:
        args = build_parser().parse_args(["--live"])
        command = build_monitor_args(args)

        self.assertNotIn("--demo", command)
        self.assertNotIn("--fetched-at", command)


if __name__ == "__main__":
    unittest.main()
