from __future__ import annotations

import argparse
import csv
import re
import urllib.request
from dataclasses import asdict
from datetime import datetime
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

from .models import EvidenceItem, EvidenceSource


YAHOO_FINANCE_BASE = "https://finance.yahoo.co.jp"
QUOTE_NEWS_URL = YAHOO_FINANCE_BASE + "/quote/{symbol}.T/news"


class YahooFinanceNewsParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._current_href: str | None = None
        self._current_text: list[str] = []
        self.links: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        href = dict(attrs).get("href")
        if not href:
            return
        if "/news/" not in href:
            return
        self._current_href = href
        self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._current_href:
            self._current_text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag != "a" or not self._current_href:
            return
        title = normalize_text("".join(self._current_text))
        if title:
            self.links.append((title, self._current_href))
        self._current_href = None
        self._current_text = []


def normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", unescape(value)).strip()


def normalize_symbol(symbol: str) -> str:
    return symbol[:-2] if symbol.upper().endswith(".T") else symbol


def fetch_quote_news_html(symbol: str, timeout: float = 10.0) -> str:
    normalized = normalize_symbol(symbol)
    request = urllib.request.Request(
        QUOTE_NEWS_URL.format(symbol=normalized),
        headers={
            "User-Agent": "kabu-paper-trading-bot/0.1 (+local research)",
            "Accept-Language": "ja,en-US;q=0.7,en;q=0.5",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", errors="replace")


def parse_yahoo_finance_news(
    html: str,
    symbol: str,
    fetched_at: datetime,
    max_items: int = 20,
) -> list[EvidenceItem]:
    parser = YahooFinanceNewsParser()
    parser.feed(html)

    seen: set[str] = set()
    items: list[EvidenceItem] = []
    for title, href in parser.links:
        absolute_url = urljoin(YAHOO_FINANCE_BASE, href)
        key = f"{title}|{absolute_url}"
        if key in seen:
            continue
        seen.add(key)
        items.append(
            EvidenceItem(
                timestamp=fetched_at,
                symbol=normalize_symbol(symbol),
                source=EvidenceSource.NEWS,
                title=title,
                body=title,
                url=absolute_url,
                confidence=0.75,
            )
        )
        if len(items) >= max_items:
            break
    return items


def write_evidence_csv(path: Path, items: list[EvidenceItem], overwrite: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["timestamp", "symbol", "source", "title", "body", "url", "confidence"]
    exists = path.exists() and not overwrite
    mode = "a" if exists else "w"
    with path.open(mode, encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        for item in items:
            row = asdict(item)
            row["timestamp"] = item.timestamp.isoformat()
            row["source"] = item.source.value
            writer.writerow(row)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Fetch Yahoo Finance Japan news as evidence CSV")
    parser.add_argument("--symbol", required=True, help="Japanese stock code, e.g. 7203 or 7203.T")
    parser.add_argument("--output", type=Path, default=Path("data/yahoo_evidence.csv"))
    parser.add_argument("--max-items", type=int, default=20)
    parser.add_argument("--html-file", type=Path, help="Parse a saved HTML file instead of fetching Yahoo")
    parser.add_argument("--fetched-at", help="Override timestamp for backtests, e.g. 2026-07-08T09:12:00")
    parser.add_argument("--overwrite", action="store_true", help="Replace output CSV instead of appending")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    fetched_at = datetime.fromisoformat(args.fetched_at) if args.fetched_at else datetime.now()
    if args.html_file:
        html = args.html_file.read_text(encoding="utf-8")
    else:
        html = fetch_quote_news_html(args.symbol)

    items = parse_yahoo_finance_news(html, args.symbol, fetched_at, args.max_items)
    write_evidence_csv(args.output, items, overwrite=args.overwrite)
    print(f"wrote {len(items)} yahoo finance evidence items to {args.output}")


if __name__ == "__main__":
    main()
