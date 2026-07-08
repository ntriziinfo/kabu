from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def to_float(value: object, default: float = 0.0) -> float:
    try:
        return float(str(value).replace(",", ""))
    except (TypeError, ValueError):
        return default


def to_int(value: object, default: int = 0) -> int:
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return default


def price_map(prices_path: Path) -> dict[str, float]:
    prices: dict[str, float] = {}
    for row in read_csv(prices_path):
        symbol = row.get("symbol", "")
        if symbol:
            prices[symbol] = to_float(row.get("price"))
    return prices


def build_paper_summary(
    positions_path: Path,
    orders_path: Path,
    prices_path: Path,
    state_path: Path,
) -> dict[str, float | int | str]:
    prices = price_map(prices_path)
    positions = read_csv(positions_path)
    orders = read_csv(orders_path)
    state = read_json(state_path)

    position_count = 0
    total_quantity = 0
    cost_basis = 0.0
    market_value = 0.0
    unrealized_pnl = 0.0
    total_risk_amount = 0.0

    for row in positions:
        quantity = to_int(row.get("quantity"))
        if quantity <= 0:
            continue
        entry_price = to_float(row.get("entry_price"))
        current_price = prices.get(row.get("symbol", ""), entry_price)
        position_count += 1
        total_quantity += quantity
        cost_basis += entry_price * quantity
        market_value += current_price * quantity
        unrealized_pnl += (current_price - entry_price) * quantity
        total_risk_amount += to_float(row.get("risk_amount"))

    closed_pnls = [to_float(row.get("realized_pnl")) for row in orders if str(row.get("realized_pnl", "")).strip()]
    wins = [pnl for pnl in closed_pnls if pnl > 0]
    losses = [pnl for pnl in closed_pnls if pnl < 0]
    closed_trades = len(closed_pnls)
    realized_pnl = to_float(state.get("realized_pnl"), sum(closed_pnls))
    total_pnl = realized_pnl + unrealized_pnl

    return {
        "date": str(state.get("date", "-")),
        "position_count": position_count,
        "total_quantity": total_quantity,
        "cost_basis": round(cost_basis, 2),
        "market_value": round(market_value, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "realized_pnl": round(realized_pnl, 2),
        "total_pnl": round(total_pnl, 2),
        "total_risk_amount": round(total_risk_amount, 2),
        "closed_trades": closed_trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round((len(wins) / closed_trades * 100) if closed_trades else 0.0, 2),
        "trade_count": to_int(state.get("trade_count")),
        "losing_streak": to_int(state.get("losing_streak")),
        "last_message": str(state.get("last_message", "")),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Summarize paper trading positions and PnL")
    parser.add_argument("--positions", type=Path, default=DATA_DIR / "paper_positions.csv")
    parser.add_argument("--orders", type=Path, default=DATA_DIR / "paper_orders.csv")
    parser.add_argument("--prices", type=Path, default=DATA_DIR / "runtime_prices.csv")
    parser.add_argument("--state", type=Path, default=DATA_DIR / "paper_state.json")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    summary = build_paper_summary(args.positions, args.orders, args.prices, args.state)
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
