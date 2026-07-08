from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
CONFIRM_FILE = ROOT / "CONFIRM_PAPER_ORDERS"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def append_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerows(rows)


def read_prices(path: Path) -> dict[str, float]:
    prices: dict[str, float] = {}
    for row in read_csv(path):
        try:
            prices[row["symbol"]] = float(row["price"])
        except (KeyError, ValueError):
            continue
    return prices


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def write_json(path: Path, data: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def today_key(now: datetime) -> str:
    return now.strftime("%Y-%m-%d")


def daily_state(state_path: Path, now: datetime) -> dict[str, object]:
    state = {
        "date": today_key(now),
        "realized_pnl": 0.0,
        "trade_count": 0,
        "losing_streak": 0,
        "last_message": "準備完了",
    }
    saved = read_json(state_path)
    if saved.get("date") == state["date"]:
        state.update(saved)
    return state


def risk_block_reason(
    state: dict[str, object],
    max_daily_loss: float,
    max_trades_per_day: int,
    max_losing_streak: int,
) -> str:
    realized_pnl = float(state.get("realized_pnl", 0.0))
    trade_count = int(state.get("trade_count", 0))
    losing_streak = int(state.get("losing_streak", 0))
    if realized_pnl <= -abs(max_daily_loss):
        return "日次損失上限に到達"
    if trade_count >= max_trades_per_day:
        return "1日の取引回数上限に到達"
    if losing_streak >= max_losing_streak:
        return "連敗停止に到達"
    return ""


def open_position_symbols(positions: list[dict[str, str]]) -> set[str]:
    symbols: set[str] = set()
    for row in positions:
        try:
            if int(float(row.get("quantity", "0"))) > 0:
                symbols.add(row.get("symbol", ""))
        except ValueError:
            continue
    return symbols


def evaluate_exits(
    positions: list[dict[str, str]],
    prices: dict[str, float],
    now: datetime,
) -> tuple[list[dict[str, str]], list[dict[str, object]], float, int]:
    remaining: list[dict[str, str]] = []
    orders: list[dict[str, object]] = []
    realized_total = 0.0
    losing_trades = 0

    for position in positions:
        symbol = position.get("symbol", "")
        price = prices.get(symbol)
        try:
            quantity = int(float(position.get("quantity", "0")))
            entry_price = float(position.get("entry_price", "0"))
            stop_loss_price = float(position.get("stop_loss_price", "0"))
            take_profit_price = float(position.get("take_profit_price", "0"))
        except ValueError:
            remaining.append(position)
            continue

        exit_reason = ""
        if quantity <= 0 or price is None:
            remaining.append(position)
            continue
        if price <= stop_loss_price:
            exit_reason = "損切り"
        elif price >= take_profit_price:
            exit_reason = "利確"

        if not exit_reason:
            remaining.append(position)
            continue

        realized_pnl = round((price - entry_price) * quantity, 2)
        realized_total += realized_pnl
        if realized_pnl < 0:
            losing_trades += 1
        orders.append(
            {
                "timestamp": now.isoformat(timespec="seconds"),
                "symbol": symbol,
                "name": position.get("name", ""),
                "side": "売り",
                "status": "紙約定",
                "quantity": quantity,
                "price": price,
                "estimated_notional": round(price * quantity, 2),
                "realized_pnl": realized_pnl,
                "reason": exit_reason,
            }
        )

    return remaining, orders, realized_total, losing_trades


def execute_paper_orders(
    trade_plan_path: Path,
    prices_path: Path,
    positions_path: Path,
    orders_path: Path,
    state_path: Path,
    confirmed: bool,
    require_confirmation: bool,
    max_daily_loss: float,
    max_trades_per_day: int,
    max_losing_streak: int,
    consume_confirmation: bool = True,
) -> dict[str, object]:
    now = datetime.now()
    state = daily_state(state_path, now)
    prices = read_prices(prices_path)
    positions = read_csv(positions_path)
    orders: list[dict[str, object]] = []

    positions, exit_orders, exit_pnl, exit_losses = evaluate_exits(positions, prices, now)
    orders.extend(exit_orders)
    state["realized_pnl"] = round(float(state.get("realized_pnl", 0.0)) + exit_pnl, 2)
    if exit_orders:
        state["trade_count"] = int(state.get("trade_count", 0)) + len(exit_orders)
        state["losing_streak"] = int(state.get("losing_streak", 0)) + exit_losses if exit_losses else 0

    block = risk_block_reason(state, max_daily_loss, max_trades_per_day, max_losing_streak)
    if block:
        state["last_message"] = block
        write_csv(positions_path, positions, POSITION_FIELDS)
        if orders:
            append_csv(orders_path, orders, ORDER_FIELDS)
        write_json(state_path, state)
        return {"ok": True, "message": block, "filled": len(orders), "blocked": 0}

    confirmation_available = confirmed or CONFIRM_FILE.exists()
    if require_confirmation and not confirmation_available:
        state["last_message"] = "紙注文の実行前確認待ち"
        write_csv(positions_path, positions, POSITION_FIELDS)
        if orders:
            append_csv(orders_path, orders, ORDER_FIELDS)
        write_json(state_path, state)
        return {"ok": True, "message": "紙注文の実行前確認待ち", "filled": len(orders), "blocked": 0}

    open_symbols = open_position_symbols(positions)
    blocked = 0
    for row in read_csv(trade_plan_path):
        if row.get("status") != "ready":
            continue
        symbol = row.get("symbol", "")
        if symbol in open_symbols:
            blocked += 1
            continue
        try:
            quantity = int(float(row.get("quantity", "0")))
            price = float(row.get("price", "0"))
        except ValueError:
            blocked += 1
            continue
        if quantity <= 0 or price <= 0:
            blocked += 1
            continue

        orders.append(
            {
                "timestamp": now.isoformat(timespec="seconds"),
                "symbol": symbol,
                "name": row.get("name", ""),
                "side": "買い",
                "status": "紙約定",
                "quantity": quantity,
                "price": price,
                "estimated_notional": round(price * quantity, 2),
                "realized_pnl": "",
                "reason": row.get("reason", ""),
            }
        )
        positions.append(
            {
                "timestamp": now.isoformat(timespec="seconds"),
                "symbol": symbol,
                "name": row.get("name", ""),
                "quantity": str(quantity),
                "entry_price": str(price),
                "stop_loss_price": row.get("stop_loss_price", ""),
                "take_profit_price": row.get("take_profit_price", ""),
                "risk_amount": row.get("risk_amount", ""),
                "reason": row.get("reason", ""),
            }
        )
        open_symbols.add(symbol)
        state["trade_count"] = int(state.get("trade_count", 0)) + 1

    if consume_confirmation and CONFIRM_FILE.exists():
        CONFIRM_FILE.unlink()

    state["last_message"] = f"紙約定 {len(orders)}件 / 見送り {blocked}件"
    write_csv(positions_path, positions, POSITION_FIELDS)
    if orders:
        append_csv(orders_path, orders, ORDER_FIELDS)
    write_json(state_path, state)
    return {
        "ok": True,
        "message": state["last_message"],
        "filled": len(orders),
        "blocked": blocked,
        "realized_pnl": state["realized_pnl"],
    }


POSITION_FIELDS = [
    "timestamp",
    "symbol",
    "name",
    "quantity",
    "entry_price",
    "stop_loss_price",
    "take_profit_price",
    "risk_amount",
    "reason",
]

ORDER_FIELDS = [
    "timestamp",
    "symbol",
    "name",
    "side",
    "status",
    "quantity",
    "price",
    "estimated_notional",
    "realized_pnl",
    "reason",
]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Execute paper orders from the trade plan")
    parser.add_argument("--trade-plan", type=Path, default=DATA_DIR / "trade_plan.csv")
    parser.add_argument("--prices", type=Path, default=DATA_DIR / "latest_prices.csv")
    parser.add_argument("--positions", type=Path, default=DATA_DIR / "paper_positions.csv")
    parser.add_argument("--orders", type=Path, default=DATA_DIR / "paper_orders.csv")
    parser.add_argument("--state", type=Path, default=DATA_DIR / "paper_state.json")
    parser.add_argument("--confirmed", action="store_true")
    parser.add_argument("--no-confirmation-required", action="store_true")
    parser.add_argument("--max-daily-loss", type=float, default=10000.0)
    parser.add_argument("--max-trades-per-day", type=int, default=10)
    parser.add_argument("--max-losing-streak", type=int, default=3)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    result = execute_paper_orders(
        args.trade_plan,
        args.prices,
        args.positions,
        args.orders,
        args.state,
        args.confirmed,
        not args.no_confirmation_required,
        args.max_daily_loss,
        args.max_trades_per_day,
        args.max_losing_streak,
    )
    print(result["message"])


if __name__ == "__main__":
    main()
