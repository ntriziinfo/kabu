from __future__ import annotations

import unittest
from datetime import datetime

from daytrade_bot.market_calendar import JST, is_trading_day, market_status


class MarketCalendarTest(unittest.TestCase):
    def test_july_9_2026_is_a_trading_day(self) -> None:
        self.assertTrue(is_trading_day(datetime(2026, 7, 9).date()))

    def test_july_20_2026_is_a_market_holiday(self) -> None:
        self.assertFalse(is_trading_day(datetime(2026, 7, 20).date()))

    def test_market_is_open_during_morning_session(self) -> None:
        report = market_status(datetime(2026, 7, 9, 9, 5, tzinfo=JST))

        self.assertTrue(report["is_trading_day"])
        self.assertTrue(report["is_open"])
        self.assertEqual(report["phase"], "morning")

    def test_market_is_closed_during_lunch_break(self) -> None:
        report = market_status(datetime(2026, 7, 9, 12, 0, tzinfo=JST))

        self.assertTrue(report["is_trading_day"])
        self.assertFalse(report["is_open"])
        self.assertEqual(report["phase"], "lunch_break")


if __name__ == "__main__":
    unittest.main()
