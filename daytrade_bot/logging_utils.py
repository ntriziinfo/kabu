from __future__ import annotations

import csv
from dataclasses import asdict
from pathlib import Path
from typing import Any


class CsvEventLogger:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._fieldnames = [
            "event",
            "timestamp",
            "symbol",
            "action",
            "side",
            "quantity",
            "price",
            "limit_price",
            "reason",
            "allowed",
            "block_reason",
            "score",
            "evidence_score",
            "evidence_count",
            "realized_pnl",
            "position_qty",
        ]
        if not self.path.exists():
            with self.path.open("w", encoding="utf-8", newline="") as handle:
                csv.DictWriter(handle, fieldnames=self._fieldnames).writeheader()

    def write(self, event: str, payload: Any, **extra: Any) -> None:
        data = asdict(payload) if hasattr(payload, "__dataclass_fields__") else dict(payload)
        data.update(extra)
        row = {key: data.get(key, "") for key in self._fieldnames}
        row["event"] = event
        with self.path.open("a", encoding="utf-8", newline="") as handle:
            csv.DictWriter(handle, fieldnames=self._fieldnames).writerow(row)
