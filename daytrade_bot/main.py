from __future__ import annotations

import argparse
from pathlib import Path

from .broker import LiveBrokerStub, PaperBroker
from .evidence import EvidenceScorer, read_evidence
from .logging_utils import CsvEventLogger
from .market import read_ticks
from .models import EvidenceSignal, Order, Side, Signal, SignalAction, Tick
from .risk import RiskConfig, RiskManager
from .strategy import OpeningRangeVwapBreakoutStrategy


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Paper-first day trading bot starter")
    parser.add_argument("--ticks", type=Path, required=True)
    parser.add_argument("--mode", choices=["paper", "live"], default="paper")
    parser.add_argument("--quantity", type=int, default=100)
    parser.add_argument("--log", type=Path, default=Path("logs/events.csv"))
    parser.add_argument("--evidence", type=Path)
    return parser


def combine_signals(
    tick: Tick,
    price_signal: Signal,
    evidence_signal: EvidenceSignal | None,
    position_qty: int,
) -> Signal:
    if evidence_signal and position_qty > 0 and evidence_signal.action == SignalAction.SELL:
        return Signal(
            tick.timestamp,
            tick.symbol,
            SignalAction.SELL,
            f"evidence_exit:{evidence_signal.reason}:score={evidence_signal.score}",
            tick.price,
        )

    if price_signal.action == SignalAction.BUY:
        if evidence_signal is None:
            return price_signal
        if evidence_signal.action == SignalAction.BUY:
            return Signal(
                tick.timestamp,
                tick.symbol,
                SignalAction.BUY,
                f"{price_signal.reason}+{evidence_signal.reason}:score={evidence_signal.score}",
                tick.price,
            )
        return Signal(tick.timestamp, tick.symbol, SignalAction.HOLD, "blocked_by_insufficient_evidence", tick.price)

    return price_signal


def main() -> None:
    args = build_parser().parse_args()
    broker = PaperBroker() if args.mode == "paper" else LiveBrokerStub()
    risk = RiskManager(RiskConfig())
    strategy = OpeningRangeVwapBreakoutStrategy()
    logger = CsvEventLogger(args.log)
    evidence_scorer = EvidenceScorer() if args.evidence else None
    evidence_items = sorted(read_evidence(args.evidence), key=lambda item: item.timestamp) if args.evidence else []
    evidence_index = 0

    for tick in read_ticks(args.ticks):
        while evidence_index < len(evidence_items) and evidence_items[evidence_index].timestamp <= tick.timestamp:
            if evidence_scorer:
                evidence_scorer.add(evidence_items[evidence_index])
            evidence_index += 1

        position_qty = broker.position_qty(tick.symbol)
        price_signal = strategy.on_tick(tick, position_qty)
        evidence_signal = evidence_scorer.signal_for(tick.symbol, tick.timestamp) if evidence_scorer else None
        signal = combine_signals(tick, price_signal, evidence_signal, position_qty)
        logger.write("price_signal", price_signal, position_qty=position_qty)
        if evidence_signal and evidence_signal.evidence_count:
            logger.write("evidence_signal", evidence_signal, position_qty=position_qty)
        logger.write(
            "combined_signal",
            signal,
            evidence_score=evidence_signal.score if evidence_signal else "",
            evidence_count=evidence_signal.evidence_count if evidence_signal else "",
            position_qty=position_qty,
        )

        if signal.action == SignalAction.HOLD:
            continue

        side = Side.BUY if signal.action == SignalAction.BUY else Side.SELL
        quantity = args.quantity if side == Side.BUY else position_qty
        order = Order(signal.timestamp, signal.symbol, side, quantity, signal.price, signal.reason)
        allowed, block_reason = risk.check_order(order, position_qty)
        logger.write("risk_check", order, allowed=allowed, block_reason=block_reason, position_qty=position_qty)

        if not allowed:
            continue

        fill = broker.place_order(order)
        risk.record_fill(fill.realized_pnl)
        logger.write("fill", fill, position_qty=broker.position_qty(tick.symbol))


if __name__ == "__main__":
    main()
