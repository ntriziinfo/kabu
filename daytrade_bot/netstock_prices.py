from __future__ import annotations

import argparse
import csv
import re
from datetime import datetime
from pathlib import Path

from .yahoo_prices import normalize_symbol


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"

SYMBOL_HEADERS = [
    "symbol",
    "code",
    "コード",
    "銘柄コード",
    "銘柄",
    "銘柄cd",
    "銘柄コード",
]
NAME_HEADERS = ["name", "名称", "銘柄名", "企業名", "銘柄名称"]
PRICE_HEADERS = [
    "price",
    "現在値",
    "現値",
    "株価",
    "現在価格",
    "最終値",
    "約定値",
]
TIME_HEADERS = ["time", "時刻", "更新時刻", "現在値時刻", "約定時刻"]


def decode_text(path: Path) -> str:
    data = path.read_bytes()
    for encoding in ("utf-8-sig", "cp932", "shift_jis", "utf-8"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("cp932", errors="replace")


def clean_header(value: str) -> str:
    return re.sub(r"[\s\u3000_\-()（）/・.]", "", value).lower()


def find_header(headers: list[str], candidates: list[str], explicit: str | None = None) -> str | None:
    if explicit:
        explicit_clean = clean_header(explicit)
        for header in headers:
            if clean_header(header) == explicit_clean:
                return header
        return explicit

    cleaned_candidates = {clean_header(candidate) for candidate in candidates}
    for header in headers:
        cleaned = clean_header(header)
        if cleaned in cleaned_candidates:
            return header
    for header in headers:
        cleaned = clean_header(header)
        if any(candidate in cleaned for candidate in cleaned_candidates):
            return header
    return None


def parse_symbol(value: str) -> str:
    normalized = normalize_symbol(value.strip())
    match = re.search(r"\d{4}", normalized)
    return match.group(0) if match else normalized


def parse_price(value: str) -> float | None:
    text = value.strip().replace(",", "")
    if not text or text in {"-", "--", "－", "N/A"}:
        return None
    match = re.search(r"[-+]?\d+(?:\.\d+)?", text)
    if not match:
        return None
    price = float(match.group(0))
    return price if price > 0 else None


def read_symbols(path: Path | None) -> dict[str, str]:
    if path is None or not path.exists():
        return {}
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = csv.DictReader(handle)
        result: dict[str, str] = {}
        for row in rows:
            symbol = parse_symbol(row.get("symbol", ""))
            if symbol:
                result[symbol] = row.get("name", "")
        return result


def read_netstock_export(
    input_path: Path,
    symbols_path: Path | None = None,
    price_column: str | None = None,
    source: str = "netstock_realtime",
) -> list[dict[str, str]]:
    if not input_path.exists():
        raise FileNotFoundError(f"NetStock CSV was not found: {input_path}")

    text = decode_text(input_path)
    reader = csv.DictReader(text.splitlines())
    headers = list(reader.fieldnames or [])
    if not headers:
        raise ValueError(f"NetStock CSV has no header row: {input_path}")

    symbol_header = find_header(headers, SYMBOL_HEADERS)
    name_header = find_header(headers, NAME_HEADERS)
    price_header = find_header(headers, PRICE_HEADERS, explicit=price_column)
    time_header = find_header(headers, TIME_HEADERS)
    if symbol_header is None:
        raise ValueError("NetStock CSV does not contain a symbol/code column")
    if price_header is None:
        raise ValueError("NetStock CSV does not contain a current price column")

    known_symbols = read_symbols(symbols_path)
    timestamp = datetime.fromtimestamp(input_path.stat().st_mtime).isoformat(timespec="seconds")
    rows: list[dict[str, str]] = []
    for row in reader:
        symbol = parse_symbol(row.get(symbol_header, ""))
        if not symbol:
            continue
        if known_symbols and symbol not in known_symbols:
            continue
        price = parse_price(row.get(price_header, ""))
        if price is None:
            continue
        name = row.get(name_header, "") if name_header else ""
        rows.append(
            {
                "symbol": symbol,
                "name": name or known_symbols.get(symbol, ""),
                "price": str(price),
                "timestamp": timestamp,
                "source": source,
                "quote_time": row.get(time_header, "") if time_header else "",
                "source_file": str(input_path),
            }
        )
    return rows


def write_prices(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = ["symbol", "name", "price", "timestamp", "source", "quote_time", "source_file"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def update_prices_from_netstock(
    input_path: Path,
    output_path: Path,
    symbols_path: Path | None = None,
    price_column: str | None = None,
    source: str = "netstock_realtime",
) -> list[dict[str, str]]:
    rows = read_netstock_export(input_path, symbols_path, price_column, source)
    write_prices(output_path, rows)
    return rows


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Import realtime prices from a NetStock High Speed CSV export")
    parser.add_argument("--input", type=Path, default=DATA_DIR / "netstock_export.csv")
    parser.add_argument("--output", type=Path, default=DATA_DIR / "runtime_prices.csv")
    parser.add_argument("--symbols", type=Path, default=DATA_DIR / "symbols.csv")
    parser.add_argument("--price-column", help="Override current-price column name if NetStock exports a custom header")
    parser.add_argument("--source", default="netstock_realtime")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    rows = update_prices_from_netstock(args.input, args.output, args.symbols, args.price_column, args.source)
    print(f"wrote {len(rows)} NetStock price rows")


if __name__ == "__main__":
    main()
