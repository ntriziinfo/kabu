from __future__ import annotations

from .broker import Broker
from .models import Fill, Order
from .netstock_highspeed import NetStockHighSpeedConfig, get_status, load_config


class NetStockHighSpeedBroker(Broker):
    """Adapter boundary for future NetStock High Speed screen automation."""

    def __init__(self, config: NetStockHighSpeedConfig | None = None) -> None:
        self.config = config or load_config()

    def position_qty(self, symbol: str) -> int:
        raise RuntimeError(
            "NetStock position reading is not implemented yet. "
            "Use paper mode until screen inspection is mapped."
        )

    def place_order(self, order: Order) -> Fill:
        if not self.config.live_trading_enabled:
            raise RuntimeError("Live trading is disabled in config/netstock_highspeed.json.")

        status = get_status(self.config)
        if not status.exe_exists:
            raise RuntimeError(f"NetStock High Speed executable was not found: {status.exe_path}")
        if not status.is_running:
            raise RuntimeError("NetStock High Speed is not running.")

        raise RuntimeError(
            "NetStock order placement is not implemented yet. "
            "The next step is mapping the order window controls safely."
        )

