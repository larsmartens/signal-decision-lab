# Krown video experiment

The question is whether a coarse reading of Krown's own Bitcoin commentary adds
useful direction beyond price history. This experiment uses regular analysis
videos and completed livestreams from `@ECKrown`. It tests a transcript feature,
not a reconstruction of his trading record.

## Before measuring returns

`sources.json` fixes 36 sources by publication date and content type. Twelve
September sources form the development set; 24 October–November sources form the
holdout. Within each content type, equally spaced date ranks select the sources.
Selection uses titles, duration and dates, never price outcomes. Failed downloads
are retained as failures rather than replaced. All 36 selected captions were
acquired successfully.

`protocol.json` fixes the six strategy variants, two cost settings, sample windows,
extractor thresholds and benchmarks. Its source, acquisition and market hashes
bind the run to these inputs. The extractor's semantic rules may be corrected
using development text and synthetic examples before its code hash is frozen.
No holdout text or empirical strategy returns are used to make those corrections.
This is a local, dated research protocol, not a registered prospective trial.

## What becomes a research event

The word-count baseline deliberately ignores most semantic distinctions. Three
context variants progressively admit a wider set of present Bitcoin views. They
exclude supported cases of negation, historical discussion, conditions, reported
speech and other assets. The parser is a hand-written English heuristic; its
errors must be measured separately from returns.

Each distinct clause contributes at most its strongest cue in each direction.
The signed score is `(long weight - short weight) / total weight`. A tie, too few
supporting clauses or insufficient dominance yields no position. The score is
not a probability. It never changes position size. Configuration values and rule
weights are recorded in JSON rather than inferred from the eventual results.

The old literal extractor is also run for coverage: it needs a source-stated
trigger, stop, target, candle interval and expiry. Its claims remain unreviewed.
A directional view is never promoted into one of those executable claims.

## Historical availability and execution

The real retrieval times remain in `acquisition.json`. For the retrospective
simulation, a normal video becomes available after publication, its full duration
and 15 minutes of processing. A completed stream becomes available 15 minutes
after the later of archive publication and verified stream end. This is an
archive-processing assumption. It does not simulate acting during a live stream
or establish that today's captions existed unchanged at publication.

Entry uses the first hourly open strictly after that time. The breakout variant
requires a completed post-availability close beyond the previous 24 completed
hours' highs or lows, followed by the next contiguous open. It waits at most 24
hours. A position lasts 24 or 48 hours. These horizons, the market mapping to
Binance spot BTCUSDT, and the position sizing are choices made by this experiment.
They are not trading instructions attributed to the speaker.

Every partition starts with 10,000 USDT. A position uses the available equity,
including entry fees, with no concurrent position or leverage. Overlapping
events are recorded and skipped. Long/short P&L is a directional proxy on spot
prices; short borrowing, funding and execution feasibility are not modeled.
Base costs are 10 basis points of fees plus 5 of adverse slippage on each
executed leg. Stress costs double both. An open final position is marked at the
last completed close, with no invented sale or exit fee.

The development window begins September 8 at 18:00 UTC and ends October 1 at
19:00 UTC. Holdout begins then and ends November 13 at 23:00 UTC. The last
development source precedes the first holdout source by more than 72 hours;
the longest confirmation-plus-holding path therefore does not cross the split.
Earlier market bars can warm an indicator, but earlier source positions cannot
carry into holdout. Missing candles are not filled.

## Comparisons and reporting

All six variants run in both windows at both cost settings: 24 declared runs.
Each is compared with buying Bitcoin at the window's first open and with a
24-hour price-momentum rule at the same video availability times. Momentum also
uses clocks where the transcript abstains. It has the same holding period and
costs, but no breakout gate; this difference is explicit in the report.

Report net return, hourly maximum drawdown, trade count, exposure, costs,
abstentions, overlaps and source coverage. Show every configuration. No return
ranking determines which result gets published. A small retrospective corpus
cannot establish a stable edge, and a profitable word-count result would not
validate the extracted meaning.

Jev and generative extraction are recorded as unrun because no inference
credentials are configured. They are not assigned fabricated trades or returns.
The published features and market CSV allow an offline replay without API keys.
Full captions remain outside git; evidence references link back to the videos.
