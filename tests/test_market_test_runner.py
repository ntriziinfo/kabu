from __future__ import annotations

import unittest

from daytrade_bot.market_test_runner import build_autopilot_args, build_parser, decision_for_market


class MarketTestRunnerTest(unittest.TestCase):
    def test_runs_only_when_market_is_open(self) -> None:
        self.assertEqual(decision_for_market({"is_open": True, "phase": "morning"}, 0, True), "run")
        self.assertEqual(decision_for_market({"is_open": False, "phase": "pre_open"}, 0, True), "wait")

    def test_stops_after_close_once_cycles_have_run(self) -> None:
        decision = decision_for_market({"is_open": False, "phase": "closed"}, ran_cycles=1, stop_at_close=True)

        self.assertEqual(decision, "stop")

    def test_waits_after_close_when_no_cycle_has_run_yet(self) -> None:
        decision = decision_for_market({"is_open": False, "phase": "closed"}, ran_cycles=0, stop_at_close=True)

        self.assertEqual(decision, "wait")

    def test_autopilot_args_use_market_test_files(self) -> None:
        args = build_parser().parse_args([])
        command = [item.replace("\\", "/") for item in build_autopilot_args(args)]

        self.assertIn("--live", command)
        self.assertIn("--require-market-open", command)
        self.assertIn("market_scan_evidence.csv", " ".join(command))
        self.assertIn("market_paper_state.json", " ".join(command))


if __name__ == "__main__":
    unittest.main()
