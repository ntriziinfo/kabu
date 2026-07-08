from __future__ import annotations

from dataclasses import dataclass

from .models import Fill, Order, Side


class Broker:
    def place_order(self, order: Order) -> Fill:
        raise NotImplementedError

    def position_qty(self, symbol: str) -> int:
        raise NotImplementedError


@dataclass
class Position:
    quantity: int = 0
    average_price: float = 0.0


class PaperBroker(Broker):
    def __init__(self, slippage_pct: float = 0.0005) -> None:
        self.slippage_pct = slippage_pct
        self.positions: dict[str, Position] = {}

    def position_qty(self, symbol: str) -> int:
        return self.positions.get(symbol, Position()).quantity

    def place_order(self, order: Order) -> Fill:
        position = self.positions.setdefault(order.symbol, Position())
        fill_price = self._fill_price(order)
        realized_pnl = 0.0

        if order.side == Side.BUY:
            new_qty = position.quantity + order.quantity
            position.average_price = (
                (position.average_price * position.quantity) + (fill_price * order.quantity)
            ) / new_qty
            position.quantity = new_qty
        else:
            sell_qty = min(order.quantity, position.quantity)
            realized_pnl = (fill_price - position.average_price) * sell_qty
            position.quantity -= sell_qty
            if position.quantity == 0:
                position.average_price = 0.0

        return Fill(order.timestamp, order.symbol, order.side, order.quantity, fill_price, realized_pnl)

    def _fill_price(self, order: Order) -> float:
        if order.side == Side.BUY:
            return order.limit_price * (1 + self.slippage_pct)
        return order.limit_price * (1 - self.slippage_pct)


class LiveBrokerStub(Broker):
    def place_order(self, order: Order) -> Fill:
        raise RuntimeError("Live trading is disabled. Implement a broker adapter after paper validation.")

    def position_qty(self, symbol: str) -> int:
        raise RuntimeError("Live trading is disabled. Implement a broker adapter after paper validation.")

