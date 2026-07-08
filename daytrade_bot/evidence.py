from __future__ import annotations

import csv
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path

from .models import EvidenceItem, EvidenceSignal, EvidenceSource, SignalAction


POSITIVE_KEYWORDS = {
    "上方修正": 2.2,
    "増配": 1.8,
    "自社株買い": 1.8,
    "大型受注": 1.5,
    "提携": 1.1,
    "承認": 1.2,
    "最高益": 1.6,
}

NEGATIVE_KEYWORDS = {
    "下方修正": -2.2,
    "減配": -1.8,
    "赤字": -1.5,
    "不正": -2.0,
    "否定": -1.2,
    "訴訟": -1.1,
    "停止": -1.0,
}

SOURCE_WEIGHTS = {
    EvidenceSource.TDNET: 1.2,
    EvidenceSource.EDINET: 1.1,
    EvidenceSource.NEWS: 1.0,
    EvidenceSource.SOCIAL: 0.45,
    EvidenceSource.MANUAL: 0.8,
}


def read_evidence(path: Path) -> list[EvidenceItem]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        return [
            EvidenceItem(
                timestamp=datetime.fromisoformat(row["timestamp"]),
                symbol=row["symbol"],
                source=EvidenceSource(row["source"]),
                title=row["title"],
                body=row["body"],
                url=row["url"],
                confidence=float(row["confidence"]),
            )
            for row in reader
        ]


class EvidenceScorer:
    def __init__(
        self,
        lookback_minutes: int = 30,
        buy_threshold: float = 2.2,
        sell_threshold: float = -2.0,
    ) -> None:
        self.lookback = timedelta(minutes=lookback_minutes)
        self.buy_threshold = buy_threshold
        self.sell_threshold = sell_threshold
        self.items_by_symbol: dict[str, list[EvidenceItem]] = defaultdict(list)

    def add(self, item: EvidenceItem) -> None:
        self.items_by_symbol[item.symbol].append(item)

    def signal_for(self, symbol: str, at: datetime) -> EvidenceSignal:
        items = [
            item for item in self.items_by_symbol.get(symbol, [])
            if at - self.lookback <= item.timestamp <= at
        ]
        score = round(sum(self._score_item(item) for item in items), 3)

        if score >= self.buy_threshold:
            action = SignalAction.BUY
            reason = "positive_evidence_cluster"
        elif score <= self.sell_threshold:
            action = SignalAction.SELL
            reason = "negative_evidence_cluster"
        else:
            action = SignalAction.HOLD
            reason = "insufficient_evidence_score"

        return EvidenceSignal(at, symbol, action, score, reason, len(items))

    def _score_item(self, item: EvidenceItem) -> float:
        text = f"{item.title} {item.body}"
        keyword_score = 0.0
        for keyword, value in POSITIVE_KEYWORDS.items():
            if keyword in text:
                keyword_score += value
        for keyword, value in NEGATIVE_KEYWORDS.items():
            if keyword in text:
                keyword_score += value

        return keyword_score * SOURCE_WEIGHTS[item.source] * item.confidence

