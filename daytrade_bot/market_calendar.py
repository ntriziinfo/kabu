from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, time
from zoneinfo import ZoneInfo


JST = ZoneInfo("Asia/Tokyo")
MORNING_OPEN = time(9, 0)
MORNING_CLOSE = time(11, 30)
AFTERNOON_OPEN = time(12, 30)
AFTERNOON_CLOSE = time(15, 30)

JPX_HOLIDAYS = {
    date(2026, 1, 1),
    date(2026, 1, 2),
    date(2026, 1, 3),
    date(2026, 1, 12),
    date(2026, 2, 11),
    date(2026, 2, 23),
    date(2026, 3, 20),
    date(2026, 4, 29),
    date(2026, 5, 3),
    date(2026, 5, 4),
    date(2026, 5, 5),
    date(2026, 5, 6),
    date(2026, 7, 20),
    date(2026, 8, 11),
    date(2026, 9, 21),
    date(2026, 9, 22),
    date(2026, 9, 23),
    date(2026, 10, 12),
    date(2026, 11, 3),
    date(2026, 11, 23),
    date(2026, 12, 31),
    date(2027, 1, 1),
    date(2027, 1, 2),
    date(2027, 1, 3),
    date(2027, 1, 11),
    date(2027, 2, 11),
    date(2027, 2, 23),
    date(2027, 3, 21),
    date(2027, 3, 22),
    date(2027, 4, 29),
    date(2027, 5, 3),
    date(2027, 5, 4),
    date(2027, 5, 5),
    date(2027, 7, 19),
    date(2027, 8, 11),
    date(2027, 9, 20),
    date(2027, 9, 23),
    date(2027, 10, 11),
    date(2027, 11, 3),
    date(2027, 11, 23),
    date(2027, 12, 31),
}


def parse_datetime(value: str | None) -> datetime:
    if not value:
        return datetime.now(tz=JST)
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=JST)
    return parsed.astimezone(JST)


def is_trading_day(day: date) -> bool:
    return day.weekday() < 5 and day not in JPX_HOLIDAYS


def market_phase(now: datetime) -> tuple[str, bool, str]:
    current = now.time()
    if MORNING_OPEN <= current <= MORNING_CLOSE:
        return "morning", True, "market_open_morning"
    if AFTERNOON_OPEN <= current <= AFTERNOON_CLOSE:
        return "afternoon", True, "market_open_afternoon"
    if current < MORNING_OPEN:
        return "pre_open", False, "before_market_open"
    if MORNING_CLOSE < current < AFTERNOON_OPEN:
        return "lunch_break", False, "lunch_break"
    return "closed", False, "after_market_close"


def market_status(as_of: datetime | None = None) -> dict[str, object]:
    now = as_of.astimezone(JST) if as_of else datetime.now(tz=JST)
    day = now.date()
    trading_day = is_trading_day(day)
    if not trading_day:
        phase, market_open, message = "holiday", False, "market_holiday"
    else:
        phase, market_open, message = market_phase(now)
    return {
        "date": day.isoformat(),
        "as_of": now.isoformat(timespec="seconds"),
        "timezone": "Asia/Tokyo",
        "is_trading_day": trading_day,
        "is_open": market_open,
        "phase": phase,
        "message": message,
        "sessions": [
            {"name": "morning", "start": "09:00", "end": "11:30"},
            {"name": "afternoon", "start": "12:30", "end": "15:30"},
        ],
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Check JPX cash equity market status")
    parser.add_argument("--as-of", help="ISO datetime in JST, e.g. 2026-07-09T09:05:00")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    report = market_status(parse_datetime(args.as_of))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["is_trading_day"] else 1


if __name__ == "__main__":
    sys.exit(main())
