# Historical market data

The retained dataset contains 3,263 hourly Binance spot BTCUSDT candles from
1 July 2026 at 00:00 UTC through the exclusive boundary 13 November 2026 at 23:00 UTC.
The final candle opens at 22:00 UTC. There are no missing hours or imputed prices.
The [published CSV](../../datasets/krown-20261113/market-bars.csv) and
[acquisition manifest](../../datasets/krown-20261113/market-provenance.json) retain the
actual prices and their provenance.

The former word-based event backtest and its outputs have been removed. These candles
remain a source dataset. No semantic claim backtest has been run against them.

## Instrument and timing

| Property | Value |
| --- | --- |
| Venue and market | Binance spot |
| Symbol | `BTCUSDT` |
| Price unit | USDT per BTC |
| Volume unit | BTC |
| Candle interval | One hour, UTC |
| First candle open | `2026-07-01T00:00:00Z` |
| Last candle open | `2026-11-13T22:00:00Z` |
| Exclusive data boundary | `2026-11-13T23:00:00Z` |
| Captured candles | 3,263 |
| Missing or imputed candles | 0 |

The exchange clock returned `2026-11-13T23:09:20.093000Z` before acquisition. The
still-open 23:00 candle and subsequent observations were excluded. Instrument metadata
was checked against the exchange's `exchangeInfo` response. This is a BTCUSDT spot
series, so a future experiment on BTCUSD, a derivative or another ticker needs a
matching dataset and explicit conversion assumptions.

## Acquisition and integrity

The fetcher uses Binance's public market-data host without account authentication.
[Binance's market-data documentation](https://developers.binance.com/en/docs/products/spot/faqs/market_data_only)
identifies the host and available endpoints. The
[spot candle reference](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market#klinecandlestick-data)
documents the response fields and pagination limits.

```bash
python scripts/fetch_market_bars.py \
  --start 2026-07-01T00:00:00Z \
  --end 2026-11-13T23:00:00Z \
  --output data/market/binance-btcusdt-1h
```

The output includes `bars.json`, `bars.csv`, `manifest.json` and raw response bodies.
The manifest records request URLs and response hashes. The script checks hourly
alignment, completed candles, consistent positive OHLC values and nonnegative volume.
It converts Binance's inclusive closing millisecond to an exclusive candle boundary.
A requested end after the latest completed hour is rejected.

| Captured artifact | SHA-256 |
| --- | --- |
| Normalized JSON | `19844ddef21c303881ab27d509b88fb7f28f739ded3ca3ea7745c4f889e37e58` |
| Published CSV | `c764e5ddbef8bcca557964d924ce2b369d1f1d24c6e9bd21587cf17109f36e27` |

The published CSV preserves its original CRLF line endings. Compare file bytes when
checking its hash. A future download may differ if the venue corrects historical data.
The acquisition is a later capture of historical candles; it is not evidence that the
project observed the market or the source commentary at the time.

## Requirements for a future semantic backtest

First define how a reviewed scenario's actual conditions become observable. Match the
ticker, venue, chart interval and forecast horizon. Keep entry triggers, invalidations
and targets in their stated roles. Any additional holding rule must be recorded as a
research choice.

Use only completed bars available at the decision, account for both execution legs,
and preserve unresolved gaps and intrabar ambiguity. Borrowing, funding, collateral
and liquidation need their own model before drawing conclusions about derivatives.
The separate synthetic paper harness checks basic execution mechanics; it provides
no empirical result for the current Krown interpretations. See the
[evaluation protocol](../EVALUATION.md) before using this dataset for a trading claim.
