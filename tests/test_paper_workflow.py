from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from daytrade_bot.paper_execution import execute_paper_orders
from daytrade_bot.paper_summary import build_paper_summary
from daytrade_bot.trade_plan import build_trade_plan


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class PaperWorkflowTest(unittest.TestCase):
    def test_trade_plan_adds_lot_size_and_risk_levels(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            candidates = root / "candidates.csv"
            prices = root / "prices.csv"
            output = root / "trade_plan.csv"

            write_csv(
                candidates,
                [
                    {
                        "timestamp": "2026-07-08T09:12:00",
                        "symbol": "7203",
                        "name": "Toyota",
                        "action": "buy",
                        "score": "2.5",
                        "evidence_count": "2",
                        "reason": "positive_evidence_cluster",
                        "top_titles": "good news",
                    }
                ],
                ["timestamp", "symbol", "name", "action", "score", "evidence_count", "reason", "top_titles"],
            )
            write_csv(prices, [{"symbol": "7203", "price": "1000"}], ["symbol", "price"])

            rows = build_trade_plan(candidates, prices, output, 2.2, 250000, 100, 0.02, 0.04)

            self.assertEqual(rows[0]["status"], "ready")
            self.assertEqual(rows[0]["quantity"], "200")
            self.assertEqual(rows[0]["stop_loss_price"], "980.0")
            self.assertEqual(rows[0]["take_profit_price"], "1040.0")
            self.assertEqual(rows[0]["risk_amount"], "4000.0")

    def test_paper_execution_waits_for_confirmation_before_new_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trade_plan = root / "trade_plan.csv"
            prices = root / "prices.csv"
            positions = root / "positions.csv"
            orders = root / "orders.csv"
            state = root / "state.json"

            write_trade_plan(trade_plan)
            write_csv(prices, [{"symbol": "7203", "price": "1000"}], ["symbol", "price"])

            result = execute_paper_orders(
                trade_plan,
                prices,
                positions,
                orders,
                state,
                confirmed=False,
                require_confirmation=True,
                max_daily_loss=10000,
                max_trades_per_day=10,
                max_losing_streak=3,
                consume_confirmation=False,
            )

            self.assertEqual(result["filled"], 0)
            self.assertEqual(read_csv(positions), [])

            result = execute_paper_orders(
                trade_plan,
                prices,
                positions,
                orders,
                state,
                confirmed=True,
                require_confirmation=True,
                max_daily_loss=10000,
                max_trades_per_day=10,
                max_losing_streak=3,
                consume_confirmation=False,
            )

            self.assertEqual(result["filled"], 1)
            self.assertEqual(read_csv(positions)[0]["symbol"], "7203")
            self.assertEqual(read_csv(orders)[0]["quantity"], "100")

    def test_take_profit_exit_updates_realized_pnl_and_summary(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            trade_plan = root / "trade_plan.csv"
            prices = root / "prices.csv"
            positions = root / "positions.csv"
            orders = root / "orders.csv"
            state = root / "state.json"

            write_empty_trade_plan(trade_plan)
            write_csv(prices, [{"symbol": "7203", "price": "1050"}], ["symbol", "price"])
            write_csv(
                positions,
                [
                    {
                        "timestamp": "2026-07-08T09:30:00",
                        "symbol": "7203",
                        "name": "Toyota",
                        "quantity": "100",
                        "entry_price": "1000",
                        "stop_loss_price": "980",
                        "take_profit_price": "1040",
                        "risk_amount": "2000",
                        "reason": "test",
                    }
                ],
                [
                    "timestamp",
                    "symbol",
                    "name",
                    "quantity",
                    "entry_price",
                    "stop_loss_price",
                    "take_profit_price",
                    "risk_amount",
                    "reason",
                ],
            )
            state.write_text(
                json.dumps({"date": "2026-07-08", "realized_pnl": 0, "trade_count": 0, "losing_streak": 0}),
                encoding="utf-8",
            )

            result = execute_paper_orders(
                trade_plan,
                prices,
                positions,
                orders,
                state,
                confirmed=False,
                require_confirmation=False,
                max_daily_loss=10000,
                max_trades_per_day=10,
                max_losing_streak=3,
                consume_confirmation=False,
            )
            summary = build_paper_summary(positions, orders, prices, state)

            self.assertEqual(result["filled"], 1)
            self.assertEqual(read_csv(positions), [])
            self.assertEqual(summary["realized_pnl"], 5000.0)
            self.assertEqual(summary["position_count"], 0)
            self.assertEqual(summary["closed_trades"], 1)
            self.assertEqual(summary["win_rate_pct"], 100.0)


def write_trade_plan(path: Path) -> None:
    write_csv(
        path,
        [
            {
                "timestamp": "2026-07-08T09:12:00",
                "symbol": "7203",
                "name": "Toyota",
                "side": "buy",
                "status": "ready",
                "block_reason": "ok",
                "score": "2.5",
                "evidence_count": "2",
                "price": "1000",
                "quantity": "100",
                "max_notional": "500000",
                "estimated_notional": "100000",
                "stop_loss_price": "980",
                "take_profit_price": "1040",
                "risk_amount": "2000",
                "reason": "positive_evidence_cluster",
                "top_titles": "good news",
            }
        ],
        trade_plan_fields(),
    )


def write_empty_trade_plan(path: Path) -> None:
    write_csv(path, [], trade_plan_fields())


def trade_plan_fields() -> list[str]:
    return [
        "timestamp",
        "symbol",
        "name",
        "side",
        "status",
        "block_reason",
        "score",
        "evidence_count",
        "price",
        "quantity",
        "max_notional",
        "estimated_notional",
        "stop_loss_price",
        "take_profit_price",
        "risk_amount",
        "reason",
        "top_titles",
    ]


if __name__ == "__main__":
    unittest.main()
