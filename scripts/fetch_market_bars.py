#!/usr/bin/env python3
"""Fetch completed Binance spot hourly candles without credentials or gap filling.

Uses urllib's default proxy handling and TLS verification. The raw API responses,
request URLs, SHA-256 digests, exchange metadata, and normalization are retained in
the output directory. Source: https://developers.binance.com/en/docs/products/spot/faqs/market_data_only
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import re
from typing import Any
import urllib.parse
import urllib.request


BASE = "https://data-api.binance.vision"
HOUR_MS = 3_600_000
FIELDS = ("asset", "open_time", "close_time", "open", "high", "low", "close", "volume")


def timestamp(value: str) -> datetime:
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError("Timestamps must include a UTC offset")
    return result.astimezone(timezone.utc)


def iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def from_ms(value: int) -> datetime:
    return datetime.fromtimestamp(value / 1000, timezone.utc)


def request_json(path: str, params: dict[str, Any] | None = None) -> tuple[Any, bytes, str]:
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "signal-decision-lab-research/0.1"})
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read()
    return json.loads(body), body, url


def normalize_row(row: list, symbol: str) -> dict:
    if not isinstance(row, list) or len(row) != 12:
        raise ValueError("Expected a twelve-field Binance kline")
    opened, closed = row[0], row[6]
    if type(opened) is not int or type(closed) is not int:
        raise ValueError("Kline timestamps must be integer milliseconds")
    if opened % HOUR_MS or closed != opened + HOUR_MS - 1:
        raise ValueError("Expected UTC-aligned complete hourly candle boundaries")
    values = [Decimal(str(value)) for value in row[1:6]]
    if any(not value.is_finite() for value in values):
        raise ValueError("Non-finite OHLCV")
    opn, high, low, close, volume = values
    if min(opn, high, low, close) <= 0 or volume < 0:
        raise ValueError("Invalid OHLCV signs")
    if low > min(opn, close) or high < max(opn, close) or low > high:
        raise ValueError("Inconsistent OHLC prices")
    return {"asset": symbol, "open_time": iso(from_ms(opened)),
            "close_time": iso(from_ms(closed + 1)),
            **{field: float(value) for field, value in zip(FIELDS[3:], values)}}


def fetch(start: datetime, end: datetime, output: Path, symbol: str = "BTCUSDT") -> dict:
    start, end = timestamp(iso(start)), timestamp(iso(end))
    if not re.fullmatch(r"[A-Z0-9]{3,20}", symbol):
        raise ValueError("Invalid exchange symbol")
    start_ms, end_ms = int(start.timestamp() * 1000), int(end.timestamp() * 1000)
    if start >= end or start_ms % HOUR_MS or end_ms % HOUR_MS:
        raise ValueError("Require start < end, both exactly on UTC hour boundaries")

    clock, clock_raw, clock_url = request_json("/api/v3/time")
    completed_until_ms = int(clock["serverTime"]) // HOUR_MS * HOUR_MS
    if end_ms > completed_until_ms:
        raise ValueError(f"Requested end exceeds latest completed boundary {iso(from_ms(completed_until_ms))}")
    exchange, exchange_raw, exchange_url = request_json("/api/v3/exchangeInfo", {"symbol": symbol})
    matches = [item for item in exchange.get("symbols", []) if item.get("symbol") == symbol]
    if len(matches) != 1 or not matches[0].get("isSpotTradingAllowed"):
        raise ValueError("Symbol is not documented as spot-tradable by exchangeInfo")
    instrument = matches[0]
    output.mkdir(parents=True, exist_ok=True)
    raw_dir = output / "raw"
    raw_dir.mkdir(exist_ok=True)
    requests = []

    def save_raw(name: str, body: bytes, url: str) -> None:
        location = raw_dir / name
        location.write_bytes(body)
        requests.append({"url": url, "file": str(location.relative_to(output)),
                         "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)})

    save_raw("server-time.json", clock_raw, clock_url)
    save_raw("exchange-info.json", exchange_raw, exchange_url)
    cursor, rows, seen = start_ms, [], set()
    while cursor < end_ms:
        data, body, url = request_json("/api/v3/klines", {
            "symbol": symbol, "interval": "1h", "startTime": cursor,
            "endTime": end_ms - 1, "limit": 1000, "timeZone": "0"})
        save_raw(f"klines-{len(requests) - 1:03d}.json", body, url)
        if not isinstance(data, list):
            raise ValueError("Exchange returned a non-array kline response")
        if not data:
            break
        previous = cursor - HOUR_MS
        for row in data:
            bar = normalize_row(row, symbol)
            opened = row[0]
            if opened in seen or opened <= previous or opened < cursor or opened >= end_ms:
                raise ValueError("Duplicate, unsorted, or out-of-request candle")
            rows.append(bar)
            seen.add(opened)
            previous = opened
        cursor = data[-1][0] + HOUR_MS

    gaps = []
    expected = start
    for row in rows:
        opened = timestamp(row["open_time"])
        if opened != expected:
            gaps.append({"start": iso(expected), "end": iso(opened),
                         "missing_bars": int((opened - expected) / timedelta(hours=1))})
        expected = timestamp(row["close_time"])
    if expected < end:
        gaps.append({"start": iso(expected), "end": iso(end),
                     "missing_bars": int((end - expected) / timedelta(hours=1))})
    json_path, csv_path = output / "bars.json", output / "bars.csv"
    json_path.write_text(json.dumps(rows, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    with csv_path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    manifest = {
        "schema_version": 1, "venue": "Binance", "market": "spot", "symbol": symbol,
        "base_asset": instrument["baseAsset"], "quote_asset": instrument["quoteAsset"],
        "price_unit": f"{instrument['quoteAsset']} per {instrument['baseAsset']}",
        "volume_unit": instrument["baseAsset"], "interval": "1h", "timezone": "UTC",
        "requested_start": iso(start), "requested_end_exclusive": iso(end),
        "exchange_server_time": iso(from_ms(clock["serverTime"])),
        "fetched_at": iso(datetime.now(timezone.utc)),
        "first_open": rows[0]["open_time"] if rows else None,
        "last_open": rows[-1]["open_time"] if rows else None,
        "last_close_exclusive": rows[-1]["close_time"] if rows else None,
        "bar_count": len(rows), "expected_bars": (end_ms - start_ms) // HOUR_MS,
        "gaps": gaps, "imputed_bars": 0,
        "normalization": "Raw API milliseconds; close_time + 1ms is the exclusive hourly boundary. No candles filled.",
        "documentation": [
            "https://developers.binance.com/en/docs/products/spot/faqs/market_data_only",
            "https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market#klinecandlestick-data",
        ],
        "requests": requests,
        "outputs": {name: {"file": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                    for name, path in (("json", json_path), ("csv", csv_path))},
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="Inclusive UTC-hour ISO timestamp")
    parser.add_argument("--end", required=True, help="Exclusive completed UTC-hour ISO timestamp")
    parser.add_argument("--symbol", default="BTCUSDT")
    parser.add_argument("--output", type=Path, default=Path("data/market/binance-btcusdt-1h"))
    args = parser.parse_args()
    manifest = fetch(timestamp(args.start), timestamp(args.end), args.output, args.symbol)
    print(json.dumps({key: manifest[key] for key in (
        "symbol", "bar_count", "first_open", "last_open", "last_close_exclusive", "gaps", "outputs")}, indent=2))


if __name__ == "__main__":
    main()
