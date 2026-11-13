# Historical market data and event-backtest contract

## Observed acquisition

The research cache contains **3,263 genuine hourly Binance spot BTCUSDT candles** from **2026-07-01 00:00 UTC through 2026-11-13 23:00 UTC**, with the final time an exclusive candle boundary. The final candle opens at 2026-11-13 22:00 UTC. All 3,263 expected hours were present; there were **zero missing hours and zero imputed prices**.

The exchange clock returned `2026-11-13T23:09:20.093000Z` before the download. The cache was written at `2026-11-13T23:09:46.763254Z`. The research cutoff was frozen at `2026-11-13T23:00:00Z`; the still-open 23:00 candle and all later observations were excluded.

These observations come from the saved API responses and acquisition manifest, rather than a search snippet or generated price example. The fetch script and this document are tracked. The reproducible market cache remains under the repository's ignored `data/` directory.

| Property | Value |
| --- | --- |
| Venue and market | Binance spot |
| Exchange symbol | `BTCUSDT` |
| Base asset | BTC |
| Quote asset | USDT |
| Price unit | USDT per BTC |
| Volume unit | BTC |
| Interval | One hour, UTC |
| Requested start | `2026-07-01T00:00:00Z`, inclusive |
| Requested end | `2026-11-13T23:00:00Z`, exclusive |
| First candle open | `2026-07-01T00:00:00Z` |
| Last candle open | `2026-11-13T22:00:00Z` |
| Number of candles | 3,263 |
| Expected candles | 3,263 |
| Missing or imputed candles | 0 |

The instrument's base and quote assets and spot eligibility were checked against the exchange's `exchangeInfo` response. BTCUSDT is a BTC price quoted in USDT; it is not a BTCUSD series or a futures contract. The model treats USDT as its accounting unit and does not model a changing USDT/USD conversion.

## Primary API references

[Binance's market-data-only documentation](https://developers.binance.com/en/docs/products/spot/faqs/market_data_only) identifies `https://data-api.binance.vision` as an unauthenticated public market-data host and lists the time, instrument-metadata and candle endpoints used here.

[Binance's spot market API reference](https://developers.binance.com/en/docs/catalog/core-trading-spot-trading/api/rest-api/market#klinecandlestick-data) documents `GET /api/v3/klines`, the hourly interval, UTC interpretation, maximum 1,000 rows per request and returned OHLCV field positions. The download made four paginated candle requests, plus one exchange-time and one instrument-metadata request.

The REST responses used here contain Unix milliseconds. Their raw close time is the final inclusive millisecond of each candle. Normalization adds one millisecond to obtain the exclusive boundary expected by the project's `Bar` model. Each row is checked to have an exactly one-hour duration, UTC-aligned open, positive consistent OHLC values and nonnegative volume. Raw responses are preserved alongside the normalized results. The script does not use the separate downloadable archive format, whose timestamp units may differ.

## Reproduction and integrity

Run from the repository root:

```bash
python scripts/fetch_market_bars.py \
  --start 2026-07-01T00:00:00Z \
  --end 2026-11-13T23:00:00Z \
  --output data/market/binance-btcusdt-1h
```

The script uses Python's standard `urllib.request` with normal environment proxy handling and TLS verification. No credentials, brokerage connection, order submission or account authentication is involved. A requested end later than the exchange's latest completed hour is rejected.

The output directory contains `bars.json`, `bars.csv`, `manifest.json`, and the exact response bodies under `raw/`. Each manifest request records its URL, raw filename, byte count and SHA-256 hash. The normalized artifacts obtained for this study were:

| Artifact | SHA-256 |
| --- | --- |
| `bars.json` | `19844ddef21c303881ab27d509b88fb7f28f739ded3ca3ea7745c4f889e37e58` |
| `bars.csv` | `c764e5ddbef8bcca557964d924ce2b369d1f1d24c6e9bd21587cf17109f36e27` |

The source is a later retrieval of historical public candles, not a contemporaneously archived feed. Re-fetching could produce different bytes if the venue corrects historical data. Compare the hashes and manifests rather than assuming that a later download is identical. API availability is also an external dependency.

## Directional research is distinct from strict trade replay

`signal_lab.research_backtest` accepts one extraction variant's timestamped directional events and completed `Bar` objects. It does not claim that a video supplied a precise entry, stop, target or executable order. A 24-hour or 48-hour hold is a **researcher-authored exit**. It is separate from the repository's strict replay engine, which requires source-stated trade conditions.

```python
import json
from pathlib import Path

from signal_lab.models import Bar
from signal_lab.research_backtest import ResearchConfig, run_research_backtest

bars = [Bar.from_dict(row) for row in json.loads(
    Path("data/market/binance-btcusdt-1h/bars.json").read_text()
)]
config = ResearchConfig(
    holding_hours=24,
    fee_bps=10,
    slippage_bps=5,
    sample_start="2026-10-01T19:00:00Z",
    sample_end="2026-11-13T23:00:00Z",
)
# events must be the frozen, evidence-backed source events for this partition.
# result = run_research_backtest(events, bars, config)
```

Each event requires `video_id`, `available_at`, `direction` (`long`, `short`, or `flat`), `strength` between zero and one, and `variant`. An optional `asset` must match the configured instrument. Additional evidence or provenance fields are retained in `per_video`. Strength is a heuristic score, not a calibrated probability, and does not control position size.

The frozen simulation rules are:

- **Availability and entry:** wait for the first hourly open strictly after `available_at`, including when availability exactly matches an hourly boundary. Both the candle containing availability and the required next open must exist. Missing data never causes a delayed chase.
- **Sample windows:** boundaries must be observed UTC-hour boundaries. Each partition starts in cash. Events before its start or at/after its exclusive end are rejected. Use the hour containing the earliest selected availability as the start; rounding the start up would exclude that first event. Earlier price bars may warm up causal indicators. Future bars cannot affect a partition.
- **One position:** signals are processed by availability, then video ID, then variant. The first eligible event reserves the position or pending confirmation. Other overlapping events are retained as explicit rejections. Flat, stale, low-strength and disallowed short events abstain.
- **Exposure:** initial position notional plus its entry fee is capped at the configured fraction of current equity, at most 100%. Quantity stays fixed during the position. Equity compounds between positions. Time in market and the time-weighted capital allocation are reported.
- **Exit:** close at the observed hourly open after the fixed holding period. If an unexpected price-data gap occurs while holding, the event strategy closes at the next observed open and labels that exit. Any intervening loss remains in the account. No missing prices are invented.
- **Optional confirmation:** a completed post-availability hourly close must exceed the highs, or fall below the lows, of the preceding 24 completed hourly candles. The complete lookback must be contiguous. Entry is at the next contiguous open, within the configured age and confirmation windows. The threshold excludes the confirmation candle itself.
- **Costs:** every executed entry and exit pays the specified fee and adverse proportional slippage. The base case uses 10 basis points fee plus 5 basis points slippage per side; stress uses 20 plus 10 per side. These are research assumptions, not a claim about the user's actual venue fee tier or execution quality.
- **Accounting:** realized losses, unrealized losses, fees, modeled slippage, completed-close drawdown, equity observations, overlaps and per-video contributions are all retained. Negative equity cannot fund another entry. Open positions at the sample end stay marked at the last observed close; no sale or exit fee is fabricated.

The default `long_short` mode is a synthetic directional proxy using spot prices. It excludes leverage, short borrowing costs, funding payments, collateral rules and actual short availability. It is not an executable short strategy on a spot account. `long_only` holds cash when the source direction is short. Cash earns no modeled interest.

## Benchmarks and interpretation

Both benchmarks use exactly the same sample boundaries and transaction-cost assumptions as the event strategy:

1. **Buy and hold:** buy at the sample's first observed open and retain the position through the final completed close, including across any internal missing-data interval. Report the open position and its entry cost. There is no fictitious final sale.
2. **Price-only 24-hour momentum:** at each identical source availability clock, use the sign of the return across the last 24 fully completed contiguous hourly candles. The candles must be current at that clock. Hold for the same configured duration under the same direction mode and overlap policy. This benchmark includes source-flat clocks; it never reads the extracted source direction. It uses no breakout gate, including when the compared event variant does.

The public result keys are `schema_version`, `mode`, `config`, `window`, `assumptions`, `summary`, `events`, `trades`, `equity`, `drawdown`, `open_position`, `per_video`, and `benchmarks`. Benchmark keys are `buy_and_hold` and `price_only_momentum`. The reported return includes incurred costs and the last mark of any open position; a completed-trade win rate covers closed trades only.

Historical availability reconstructed from video publication and duration remains an assumption. These tests can compare frozen extraction and execution rules on retrieved history. They cannot establish that transcripts, extraction results, fills or borrowing were available in real time, nor establish profitability beyond the selected sample.

## Verification

`python -m unittest tests.test_research_backtest` covers causal entry timing, completed-bar breakout, fixed holds, realized and open-position accounting, both cost legs, long/short sign, long-only cash, overlaps, sample boundaries, future-price isolation, missing-data behavior, same-clock benchmarks, timestamp normalization, refusing incomplete future candles and preserving a download gap without imputation. All tests use artificial prices and make no empirical return claim.
