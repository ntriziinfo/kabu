from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class Side(str, Enum):
    BUY = "buy"
    SELL = "sell"


class SignalAction(str, Enum):
    HOLD = "hold"
    BUY = "buy"
    SELL = "sell"


class EvidenceSource(str, Enum):
    TDNET = "tdnet"
    EDINET = "edinet"
    NEWS = "news"
    SOCIAL = "social"
    MANUAL = "manual"


@dataclass(frozen=True)
class Tick:
    timestamp: datetime
    symbol: str
    price: float
    volume: int


@dataclass(frozen=True)
class Signal:
    timestamp: datetime
    symbol: str
    action: SignalAction
    reason: str
    price: float


@dataclass(frozen=True)
class EvidenceItem:
    timestamp: datetime
    symbol: str
    source: EvidenceSource
    title: str
    body: str
    url: str
    confidence: float


@dataclass(frozen=True)
class EvidenceSignal:
    timestamp: datetime
    symbol: str
    action: SignalAction
    score: float
    reason: str
    evidence_count: int


@dataclass(frozen=True)
class Order:
    timestamp: datetime
    symbol: str
    side: Side
    quantity: int
    limit_price: float
    reason: str


@dataclass(frozen=True)
class Fill:
    timestamp: datetime
    symbol: str
    side: Side
    quantity: int
    price: float
    realized_pnl: float
