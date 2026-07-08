from __future__ import annotations

from dataclasses import dataclass
from datetime import time
from pathlib import Path

from .models import Order, Side


@dataclass
class RiskConfig:
    max_position_qty: int = 100
    max_daily_loss: float = 10000.0
    max_trades_per_day: int = 10
    entry_cutoff: time = time(14, 30)
    stop_file: Path = Path("STOP_TRADING")


class RiskManager:
    def __init__(self, config: RiskConfig) -> None:
        self.config = config
        self.trade_count = 0
        self.realized_pnl = 0.0

    def record_fill(self, realized_pnl: float) -> None:
        self.trade_count += 1
        self.realized_pnl += realized_pnl

    def check_order(self, order: Order, current_position_qty: int) -> tuple[bool, str]:
        if self.config.stop_file.exists():
            return False, "emergency_stop_file_exists"

        if self.realized_pnl <= -abs(self.config.max_daily_loss):
            return False, "max_daily_loss_reached"

        if self.trade_count >= self.config.max_trades_per_day:
            return False, "max_trades_per_day_reached"

        if order.side == Side.BUY and order.timestamp.time() >= self.config.entry_cutoff:
            return False, "entry_cutoff_passed"

        next_position = current_position_qty + order.quantity if order.side == Side.BUY else current_position_qty - order.quantity
        if abs(next_position) > self.config.max_position_qty:
            return False, "max_position_qty_exceeded"

        if order.side == Side.SELL and current_position_qty <= 0:
            return False, "no_position_to_sell"

        return True, "ok"

