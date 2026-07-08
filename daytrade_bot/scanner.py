from __future__ import annotations

import argparse
import csv
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .evidence import EvidenceScorer
from .models import EvidenceItem
from .yahoo_finance import fetch_quote_news_html, parse_yahoo_finance_news


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"


def read_symbols(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def scan_symbol(
    symbol: str,
    fetched_at: datetime,
    demo: bool,
    max_items: int,
) -> list[EvidenceItem]:
    if demo:
        demo_html = DATA_DIR / f"sample_yahoo_finance_{symbol}.html"
        if not demo_html.exists():
            return []
        html = demo_html.read_text(encoding="utf-8")
    else:
        html = fetch_quote_news_html(symbol)
    return parse_yahoo_finance_news(html, symbol, fetched_at, max_items=max_items)


def write_evidence(path: Path, items: list[EvidenceItem]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["timestamp", "symbol", "source", "title", "body", "url", "confidence"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for item in items:
            row = asdict(item)
            row["timestamp"] = item.timestamp.isoformat()
            row["source"] = item.source.value
            writer.writerow(row)


def write_candidates(
    path: Path,
    symbols: list[dict[str, str]],
    items: list[EvidenceItem],
    at: datetime,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    scorer = EvidenceScorer()
    by_symbol: dict[str, list[EvidenceItem]] = {}
    for item in items:
        scorer.add(item)
        by_symbol.setdefault(item.symbol, []).append(item)

    rows = []
    for symbol_row in symbols:
        symbol = symbol_row["symbol"]
        signal = scorer.signal_for(symbol, at)
        titles = " | ".join(item.title for item in by_symbol.get(symbol, [])[:3])
        rows.append(
            {
                "timestamp": at.isoformat(),
                "symbol": symbol,
                "name": symbol_row.get("name", ""),
                "action": signal.action.value,
                "score": signal.score,
                "evidence_count": signal.evidence_count,
                "reason": signal.reason,
                "top_titles": titles,
            }
        )

    rows.sort(key=lambda row: float(row["score"]), reverse=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "timestamp",
                "symbol",
                "name",
                "action",
                "score",
                "evidence_count",
                "reason",
                "top_titles",
            ],
        )
        writer.writeheader()
        writer.writerows(rows)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Scan symbols for Yahoo Finance evidence candidates")
    parser.add_argument("--symbols", type=Path, default=DATA_DIR / "symbols.csv")
    parser.add_argument("--evidence-output", type=Path, default=DATA_DIR / "scan_evidence.csv")
    parser.add_argument("--candidates-output", type=Path, default=DATA_DIR / "candidates.csv")
    parser.add_argument("--max-items", type=int, default=10)
    parser.add_argument("--demo", action="store_true", help="Use saved sample HTML instead of live Yahoo requests")
    parser.add_argument("--fetched-at", help="Override timestamp, e.g. 2026-07-08T09:12:00")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    fetched_at = datetime.fromisoformat(args.fetched_at) if args.fetched_at else datetime.now()
    symbols = read_symbols(args.symbols)
    all_items: list[EvidenceItem] = []

    for symbol_row in symbols:
        symbol = symbol_row["symbol"]
        try:
            all_items.extend(scan_symbol(symbol, fetched_at, args.demo, args.max_items))
        except Exception as exc:
            print(f"scan failed for {symbol}: {exc}")

    write_evidence(args.evidence_output, all_items)
    write_candidates(args.candidates_output, symbols, all_items, fetched_at)
    print(f"scanned {len(symbols)} symbols, wrote {len(all_items)} evidence items")


if __name__ == "__main__":
    main()

