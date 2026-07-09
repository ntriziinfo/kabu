from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from daytrade_bot.netstock_prices import read_netstock_export, update_prices_from_netstock


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class NetStockPricesTest(unittest.TestCase):
    def test_imports_cp932_current_prices_from_netstock_export(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "netstock.csv"
            symbols = root / "symbols.csv"
            output = root / "prices.csv"
            source.write_text(
                "銘柄コード,銘柄名,現在値,時刻\n7203,トヨタ自動車,2,836.5,09:22\n".replace(
                    "2,836.5", '"2,836.5"'
                ),
                encoding="cp932",
            )
            symbols.write_text("symbol,name\n7203,Toyota\n", encoding="utf-8")

            rows = update_prices_from_netstock(source, output, symbols)

            self.assertEqual(rows[0]["symbol"], "7203")
            self.assertEqual(rows[0]["price"], "2836.5")
            self.assertEqual(rows[0]["source"], "netstock_realtime")
            self.assertEqual(read_csv(output)[0]["quote_time"], "09:22")

    def test_filters_to_known_symbols(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "netstock.csv"
            symbols = root / "symbols.csv"
            source.write_text(
                "コード,銘柄名,現値\n7203,Toyota,2836.5\n9999,Other,100\n",
                encoding="utf-8",
            )
            symbols.write_text("symbol,name\n7203,Toyota\n", encoding="utf-8")

            rows = read_netstock_export(source, symbols)

            self.assertEqual([row["symbol"] for row in rows], ["7203"])


if __name__ == "__main__":
    unittest.main()
