from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from datetime import time

from .models import Signal, SignalAction, Tick


@dataclass
class SymbolState:
    opening_high: float | None = None
    opening_low: float | None = None
    cumulative_price_volume: float = 0.0
    cumulative_volume: int = 0
    volumes: deque[int] = field(default_factory=deque)
    entry_price: float | None = None
    highest_since_entry: float | None = None
    traded_today: bool = False


class OpeningRangeVwapBreakoutStrategy:
    """Intraday long-only strategy using opening range, VWAP, and volume confirmation."""

    def __init__(
        self,
        opening_range_end: time = time(9, 15),
        entry_start: time = time(9, 15),
        entry_end: time = time(14, 0),
        force_exit: time = time(14, 50),
        volume_window: int = 8,
        breakout_buffer_pct: float = 0.001,
        min_volume_ratio: float = 1.2,
        take_profit_pct: float = 0.006,
        stop_loss_pct: float = 0.0035,
        trailing_stop_pct: float = 0.004,
    ) -> None:
        self.opening_range_end = opening_range_end
        self.entry_start = entry_start
        self.entry_end = entry_end
        self.force_exit = force_exit
        self.volume_window = volume_window
        self.breakout_buffer_pct = breakout_buffer_pct
        self.min_volume_ratio = min_volume_ratio
        self.take_profit_pct = take_profit_pct
        self.stop_loss_pct = stop_loss_pct
        self.trailing_stop_pct = trailing_stop_pct
        self.states: dict[str, SymbolState] = {}

    def on_tick(self, tick: Tick, position_qty: int) -> Signal:
        state = self.states.setdefault(tick.symbol, SymbolState(volumes=deque(maxlen=self.volume_window)))
        self._update_session_stats(tick, state)
        current_time = tick.timestamp.time()

        if position_qty > 0 and state.entry_price:
            state.highest_since_entry = max(state.highest_since_entry or tick.price, tick.price)
            drawdown_from_high = (tick.price - state.highest_since_entry) / state.highest_since_entry
            gain = (tick.price - state.entry_price) / state.entry_price

            if current_time >= self.force_exit:
                self._clear_position_state(state)
                return Signal(tick.timestamp, tick.symbol, SignalAction.SELL, "force_exit_before_close", tick.price)

            if gain >= self.take_profit_pct:
                self._clear_position_state(state)
                return Signal(tick.timestamp, tick.symbol, SignalAction.SELL, "take_profit", tick.price)

            if gain <= -self.stop_loss_pct:
                self._clear_position_state(state)
                return Signal(tick.timestamp, tick.symbol, SignalAction.SELL, "stop_loss", tick.price)

            if drawdown_from_high <= -self.trailing_stop_pct and gain > 0:
                self._clear_position_state(state)
                return Signal(tick.timestamp, tick.symbol, SignalAction.SELL, "trailing_stop", tick.price)

            return self._hold(tick, "holding_position")

        if current_time < self.entry_start:
            return self._hold(tick, "building_opening_range")

        if current_time > self.entry_end:
            return self._hold(tick, "entry_window_closed")

        if state.traded_today:
            return self._hold(tick, "one_trade_limit")

        if state.opening_high is None or state.cumulative_volume <= 0:
            return self._hold(tick, "insufficient_session_stats")

        vwap = state.cumulative_price_volume / state.cumulative_volume
        average_volume = sum(state.volumes) / len(state.volumes) if state.volumes else 0
        volume_ratio = tick.volume / average_volume if average_volume else 0
        breakout_price = state.opening_high * (1 + self.breakout_buffer_pct)

        if tick.price > breakout_price and tick.price > vwap and volume_ratio >= self.min_volume_ratio:
            state.entry_price = tick.price
            state.highest_since_entry = tick.price
            state.traded_today = True
            return Signal(tick.timestamp, tick.symbol, SignalAction.BUY, "opening_range_vwap_volume_breakout", tick.price)

        return self._hold(tick, "no_edge")

    def _update_session_stats(self, tick: Tick, state: SymbolState) -> None:
        state.cumulative_price_volume += tick.price * tick.volume
        state.cumulative_volume += tick.volume
        state.volumes.append(tick.volume)

        if tick.timestamp.time() <= self.opening_range_end:
            state.opening_high = tick.price if state.opening_high is None else max(state.opening_high, tick.price)
            state.opening_low = tick.price if state.opening_low is None else min(state.opening_low, tick.price)

    @staticmethod
    def _clear_position_state(state: SymbolState) -> None:
        state.entry_price = None
        state.highest_since_entry = None

    @staticmethod
    def _hold(tick: Tick, reason: str) -> Signal:
        return Signal(tick.timestamp, tick.symbol, SignalAction.HOLD, reason, tick.price)


MomentumReversalStrategy = OpeningRangeVwapBreakoutStrategy
