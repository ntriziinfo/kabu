from __future__ import annotations

import unittest

from daytrade_bot.yahoo_prices import parse_chart_price, parse_price


class YahooPricesTest(unittest.TestCase):
    def test_parse_chart_price_uses_regular_market_price(self) -> None:
        payload = {
            "chart": {
                "result": [
                    {
                        "meta": {
                            "symbol": "7203.T",
                            "regularMarketPrice": 2845.0,
                        }
                    }
                ]
            }
        }

        self.assertEqual(parse_chart_price(payload), 2845.0)

    def test_parse_price_does_not_treat_symbol_code_as_price(self) -> None:
        html = '{"price":"7203.T","currentPrice":"2,845"}'

        self.assertEqual(parse_price(html), 2845.0)


if __name__ == "__main__":
    unittest.main()
