from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .models import Tick


def read_ticks(path: Path) -> Iterator[Tick]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            yield Tick(
                timestamp=datetime.fromisoformat(row["timestamp"]),
                symbol=row["symbol"],
                price=float(row["price"]),
                volume=int(row["volume"]),
            )

