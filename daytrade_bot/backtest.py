from __future__ import annotations

import argparse
import csv
from pathlib import Path

from .main import main as run_bot


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run paper backtest and summarize fills")
    parser.add_argument("--ticks", type=Path, required=True)
    parser.add_argument("--quantity", type=int, default=100)
    parser.add_argument("--log", type=Path, default=Path("logs/backtest_events.csv"))
    parser.add_argument("--evidence", type=Path)
    return parser


def summarize(log_path: Path) -> dict[str, float | int]:
    realized = []
    equity = 0.0
    peak = 0.0
    max_drawdown = 0.0

    with log_path.open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["event"] != "fill" or not row["realized_pnl"]:
                continue
            pnl = float(row["realized_pnl"])
            if pnl == 0:
                continue
            realized.append(pnl)
            equity += pnl
            peak = max(peak, equity)
            max_drawdown = min(max_drawdown, equity - peak)

    wins = [pnl for pnl in realized if pnl > 0]
    losses = [pnl for pnl in realized if pnl < 0]
    trades = len(realized)
    return {
        "closed_trades": trades,
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_pct": round((len(wins) / trades * 100) if trades else 0.0, 2),
        "realized_pnl": round(sum(realized), 2),
        "average_win": round((sum(wins) / len(wins)) if wins else 0.0, 2),
        "average_loss": round((sum(losses) / len(losses)) if losses else 0.0, 2),
        "max_drawdown": round(max_drawdown, 2),
    }


def main() -> None:
    args = build_parser().parse_args()
    if args.log.exists():
        args.log.unlink()

    import sys

    original_argv = sys.argv
    try:
        sys.argv = [
            "daytrade_bot.main",
            "--ticks",
            str(args.ticks),
            "--mode",
            "paper",
            "--quantity",
            str(args.quantity),
            "--log",
            str(args.log),
        ]
        if args.evidence:
            sys.argv.extend(["--evidence", str(args.evidence)])
        run_bot()
    finally:
        sys.argv = original_argv

    for key, value in summarize(args.log).items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
