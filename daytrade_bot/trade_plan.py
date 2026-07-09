from __future__ import annotations

import argparse
import csv
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def read_prices(path: Path) -> dict[str, float]:
    prices: dict[str, float] = {}
    for row in read_csv(path):
        try:
            prices[row["symbol"]] = float(row["price"])
        except (KeyError, ValueError):
            continue
    return prices


def read_price_rows(path: Path) -> dict[str, dict[str, str]]:
    return {row.get("symbol", ""): row for row in read_csv(path) if row.get("symbol")}


def is_realtime_price(row: dict[str, str] | None) -> bool:
    if row is None:
        return False
    source = row.get("source", "").lower()
    return source in {"netstock", "netstock_realtime", "manual_realtime", "broker_realtime", "realtime"}


def is_fresh_price(row: dict[str, str] | None, max_age_seconds: float, now: datetime | None = None) -> bool:
    if max_age_seconds <= 0:
        return True
    if row is None:
        return False
    timestamp = row.get("timestamp", "")
    if not timestamp:
        return False
    try:
        parsed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError:
        return False
    reference = now or datetime.now(parsed.tzinfo)
    if parsed.tzinfo is None and reference.tzinfo is not None:
        reference = reference.replace(tzinfo=None)
    age = (reference - parsed).total_seconds()
    return 0 <= age <= max_age_seconds


def lot_quantity(price: float, max_notional: float, lot_size: int) -> int:
    if price <= 0:
        return 0
    lots = int(max_notional // (price * lot_size))
    return max(0, lots * lot_size)


def build_trade_plan(
    candidates_path: Path,
    prices_path: Path,
    output_path: Path,
    min_score: float,
    max_notional: float,
    lot_size: int,
    stop_loss_pct: float,
    take_profit_pct: float,
    require_realtime_prices: bool = False,
    max_realtime_price_age_seconds: float = 0.0,
) -> list[dict[str, str]]:
    candidates = read_csv(candidates_path)
    prices = read_prices(prices_path)
    price_rows = read_price_rows(prices_path)
    now = datetime.now().isoformat(timespec="seconds")
    rows: list[dict[str, str]] = []

    for candidate in candidates:
        try:
            score = float(candidate.get("score", "0"))
        except ValueError:
            score = 0.0

        symbol = candidate.get("symbol", "")
        action = candidate.get("action", "")
        price = prices.get(symbol)
        price_row = price_rows.get(symbol)
        price_is_realtime = is_realtime_price(price_row)
        price_is_fresh = is_fresh_price(price_row, max_realtime_price_age_seconds)
        quantity = lot_quantity(price, max_notional, lot_size) if price is not None else 0
        status = (
            "ready"
            if action == "buy"
            and score >= min_score
            and quantity > 0
            and (not require_realtime_prices or price_is_realtime)
            and (not require_realtime_prices or price_is_fresh)
            else "blocked"
        )
        if status == "ready" and price is not None:
            stop_loss_price = round(price * (1 - stop_loss_pct), 2)
            take_profit_price = round(price * (1 + take_profit_pct), 2)
            risk_amount = round((price - stop_loss_price) * quantity, 2)
        else:
            stop_loss_price = ""
            take_profit_price = ""
            risk_amount = ""

        if action != "buy":
            block_reason = "not_buy_candidate"
        elif score < min_score:
            block_reason = "score_below_threshold"
        elif price is None:
            block_reason = "missing_price"
        elif require_realtime_prices and not price_is_realtime:
            block_reason = "price_not_realtime"
        elif require_realtime_prices and not price_is_fresh:
            block_reason = "stale_realtime_price"
        elif quantity <= 0:
            block_reason = "max_notional_too_low"
        else:
            block_reason = "ok"

        rows.append(
            {
                "timestamp": now,
                "symbol": symbol,
                "name": candidate.get("name", ""),
                "side": "buy" if action == "buy" else "",
                "status": status,
                "block_reason": block_reason,
                "score": str(score),
                "evidence_count": candidate.get("evidence_count", "0"),
                "price": "" if price is None else str(price),
                "quantity": str(quantity),
                "max_notional": str(max_notional),
                "estimated_notional": "" if price is None else str(round(price * quantity, 2)),
                "stop_loss_price": str(stop_loss_price),
                "take_profit_price": str(take_profit_price),
                "risk_amount": str(risk_amount),
                "reason": candidate.get("reason", ""),
                "top_titles": candidate.get("top_titles", ""),
            }
        )

    rows.sort(key=lambda row: (row["status"] != "ready", -float(row["score"] or 0)))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
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
            ],
        )
        writer.writeheader()
        writer.writerows(rows)
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build paper trade plan from ranked candidates")
    parser.add_argument("--candidates", type=Path, default=DATA_DIR / "candidates.csv")
    parser.add_argument("--prices", type=Path, default=DATA_DIR / "latest_prices.csv")
    parser.add_argument("--output", type=Path, default=DATA_DIR / "trade_plan.csv")
    parser.add_argument("--min-score", type=float, default=2.2)
    parser.add_argument("--max-notional", type=float, default=500000.0)
    parser.add_argument("--lot-size", type=int, default=100)
    parser.add_argument("--stop-loss-pct", type=float, default=0.02)
    parser.add_argument("--take-profit-pct", type=float, default=0.04)
    parser.add_argument("--require-realtime-prices", action="store_true")
    parser.add_argument("--max-realtime-price-age-seconds", type=float, default=120.0)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows = build_trade_plan(
        args.candidates,
        args.prices,
        args.output,
        args.min_score,
        args.max_notional,
        args.lot_size,
        args.stop_loss_pct,
        args.take_profit_pct,
        args.require_realtime_prices,
        args.max_realtime_price_age_seconds,
    )
    ready_count = sum(1 for row in rows if row["status"] == "ready")
    print(f"wrote {len(rows)} trade plan rows, ready {ready_count}")


if __name__ == "__main__":
    main()
