# Krown directional-view extraction

## Known source interpretation failures

The [completed study](../experiments/krown-20261114/README.md) found serious source
interpretation failures in both profitable strict-rule holdout cases. An indicator
comparison and conditional future stance became current long views; MSTR/MSTZ and
Monero commentary became a Bitcoin short. The frozen rules and features remain intact
for reproduction. The synthetic checks below establish only the cases they exercise;
they do not validate these empirical source interpretations.

## Purpose and boundary

`signal_lab/krown_extract.py` extracts auditable research features from English
captions. It answers a bounded question: does the text contain a supported,
current Bitcoin directional view under a specified rule configuration?

These features are not source-authored trade instructions. The module does not
produce entries, stops, targets, order types, execution prices, or a human-review
decision. It does not call an LLM or Jev. It never creates or approves an existing
`Signal`. The separate executable baseline in `signal_lab/extract.py` retains its
existing completeness, grounding, and review gates.

The module performs deterministic language matching and scope checks. Calling
it context-aware means that its explicit English rules inspect surrounding
text; it does not mean that it understands unrestricted speech. Its positive
and negative controls, known failure cases, and limits matter more than that
label.

## Source and development boundary

The original-channel corpus and its metadata are documented in
[krown-corpus.md](krown-corpus.md). Only these twelve frozen development sources
were inspected while adapting the extractor:

```text
DyB0RL8GnhA  Wo7tnwTMYNQ  nujnKp4lVbo  8LBiM6deRks
jc2HQXgcY5s  PXWP9f2bpPU  pT7jeM9j490  UtCC3s_lo3o
sZPfKVEoK0I  mEHFdbVMyrQ  tPYEYNwhKGc  uOWagLcNLKM
```

The extraction author did not inspect holdout captions, price data, or returns.
Development changes addressed observable language problems, including caption
line wrapping, conditional context carried into a following sentence,
relative-pair discussion, indicator descriptions, and repeated captions. The
numeric configurations were selected before any market evaluation. A separate
agent challenged the public interface with synthetic transcripts and did not
read any real source or market data.

Captions are imperfect evidence of speech. Their segment timestamps are
preserved; they are not presented as exact word-level audio timestamps. The
extractor does not infer that current captions existed at the historical
publication time. It does not assign research availability: that remains the
runner's responsibility using the frozen metadata assumptions.

## Public interface

```python
from signal_lab.krown_extract import (
    BIAS_CONFIGS,
    extract_bias_events,
    aggregate_bias,
    extract_bias,
    validate_bias_grounding,
)

events = extract_bias_events(transcript, "context_standard")
summary = aggregate_bias(events, "context_standard", video_id=transcript.source_id)
same_summary = extract_bias(transcript, "context_standard")
```

The input is the existing `Transcript` type. These functions do not read files,
request a service, inspect prices, or modify the input. Dataclass outputs can
be serialized with the existing `models.jsonable` helper.

### Candidate events

Every recognized directional cue produces a `BiasEvent`, including excluded
candidates. `candidate_direction` records the vocabulary's raw orientation.
`direction` becomes `flat` and `strength` becomes zero when the event is
excluded. This makes abstention visible rather than silently dropping awkward
examples.

Each event contains the source ID, configuration, rule/version provenance,
acceptance state, reason codes, cue timestamps, a clause identifier, exact cue
spans, and full source-context spans. A span contains its segment ID, character
offsets, exact source substring, and source-segment start and end time.

`asset="BTCUSDT"` is the research runner's Bitcoin market mapping. It does not
mean that the speaker specified a USDT venue, spot transaction, or derivatives
contract. Nearby explicit derivatives vocabulary sets
`derivatives_mentioned=True`; absence of that vocabulary leaves the instrument
unspecified.

`timeframe_minutes` is a stated chart timeframe. `horizon_minutes` is a stated
fixed duration such as an explicit next-N-hours forecast. They are different
concepts. An unavailable or ambiguous value remains `None`. Calendar phrases
such as a named quarter are not converted to an invented fixed duration. A
decimal chart duration is currently unsupported and remains `None`, rather
than being misread as its fractional digit.

No event has a stop, target, executable trigger, expiry, `reviewed` field, or
calibrated probability.

### Per-video summary

`BiasSummary` reports the video ID, variant, direction, signed score, strength,
positive and negative unit counts, supporting and conflicting counts,
excluded-candidate count, reason counts, and representative evidence.

The signed score is a **heuristic balance of textual evidence**. A value of
`1.0` means that all counted weight points in the positive direction. It is not
a 100% chance of an upward market move. `strength` is the absolute balance only
when the variant passes its support and dominance gates; it is zero for a flat
decision. A strict summary can therefore have signed score `1.0` and remain
flat because only one distinct claim was available.

`validate_bias_grounding` checks source identity, exact spans and timestamps,
cue polarity, variant/rule consistency, and documented weight bounds. It is a
provenance and internal-consistency check. It does not certify general semantic
accuracy or replace a human review of the underlying statement.

## Extraction rules

The shared vocabulary includes bullish/bearish, upside/downside, higher/lower,
rally/sell-off, bounce/pullback, breakout/breakdown, dump, and explicit go-long
or go-short phrases. Vocabulary matching alone is the intentionally naive
`lexical` comparator. All variants still require a bounded Bitcoin reference
and reject recognized competing asset names or ambiguous recognized bindings.

Contextual variants additionally require a supported present stance,
expectation, probability/bias phrase, or configured descriptive rule. They
check the full relevant clause for disqualifying language even when the
positive recognition window is shorter. The full sentence and a borrowed
asset-reference sentence preserve conditional, historical, and attribution
context. One immediately following sentence or semicolon clause is also
retained when it explicitly adds a condition or correction. Caption line
breaks are treated as wrapping, not sentence endings.

The current exclusions cover:

- Negation, without reversing its meaning into an opposite forecast.
- Historical speech and past-tense expectations.
- Conditions such as if, when, unless, contingent-on, and supported threshold
  formulations. Branch conditions remain excluded rather than being turned
  into unconditional trades.
- Educational examples, hypothetical statements, unresolved corrections,
  questions, and uncertainty.
- Attributed views from named speakers, viewers, or groups of traders.
- Mere possibility such as could or might without an asserted current stance.
- Explicit first-person statements about becoming bullish or bearish later.
- Technical descriptions such as a bullish divergence or oscillator reset.
- Higher/lower timeframes, highs/lows, volatility, and similar comparisons.
- Relative views against Bitcoin, Bitcoin dominance, and other recognized
  non-price Bitcoin metrics.
- An explicitly different subject after a bullish/bearish descriptor.

These are finite rules. Unrecognized paraphrases, names, referents, sarcasm,
multi-stage scenarios, caption errors, and long-range discourse can still be
misclassified. Conservative exclusions also reject some legitimate current
views. The experiment must report abstention and coverage, not just returns
from the surviving cases.

## Frozen variants and weights

Context radius is the maximum number of words on each side of a cue for
positive-rule recognition, clipped to punctuation and contrast clauses.
Disqualifying context is deliberately wider so that a small window cannot
erase a condition or negation. Asset carry is the maximum distance to a
preceding Bitcoin reference when the current clause has no direct asset name.

| Variant | Context radius | Asset carry | Minimum supporting units | Minimum absolute balance | Accepted rule families |
|---|---:|---:|---:|---:|---|
| `lexical` | 32 | 70 | 1 | 0.00 | Directional word mention |
| `context_strict` | 24 | 40 | 2 | 0.50 | Explicit stance, explicit expectation, probability/bias |
| `context_standard` | 48 | 70 | 1 | 0.25 | Strict families plus present market description |
| `context_broad` | 80 | 100 | 1 | 0.10 | Standard families plus bounded and tentative expectations |

All exact ties remain flat, including the lexical baseline.

| Rule family | Heuristic weight |
|---|---:|
| Word mention | 1.0 |
| Explicit stance | 1.0 |
| Explicit expectation | 1.0 |
| Probability/bias language | 0.8 |
| Present market description | 0.6 |
| Bounded directional expectation | 0.5 |
| Tentative expectation | 0.4 |

These weights express an explicit ordering of textual support. They were not
fit to market outcomes and are not source-stated probabilities.

## Aggregation and abstention

Sentence punctuation and contrast markers identify source clauses. Whitespace
and punctuation normalization makes repeated identical clauses share an ID.
Within each normalized clause and direction, only the largest accepted rule
weight contributes. Repeated directional words in one clause and duplicated
identical captions therefore cannot multiply support.

Let `P` and `N` be the sums of retained positive and negative weights:

```text
signed_score = (P - N) / (P + N), or 0 when P + N = 0
```

The winning side must meet both the variant's minimum number of supporting
units and its minimum absolute balance. Otherwise the summary is flat.
Opposing claims are retained, counted, and reflected in the balance; the
extractor never chooses the statement that matches a later market outcome.

“Distinct units” means distinct normalized clauses. It does not mean
statistically independent observations. Paraphrased repetition can still count
more than once, and mixed time horizons can contribute opposing views. Both
are limitations of this bounded baseline. A fixed 24-hour or 48-hour holding
period is a runner-imposed research policy, even when a source discusses a
quarter or a longer market cycle.

## Evidence publication and copyright

Full captions and full exact event evidence belong in the ignored local data
cache. They must not be committed. A summary's optional compact excerpt is
bounded to 25 words, but this is not an additional allowance for every variant
or repeated report. Any quotation budget applies cumulatively to a source.

For this experiment, published derived features and reports use **no caption
quotations**. They retain video URLs, segment IDs, timestamps, offsets, and
seek links. Strip `quote` fields before publishing. Preserve the full internal
spans for audit and validation.

## Behavioral evidence

The extraction test module uses written synthetic text rather than copied
captions. It covers supported positive and negative views, abstentions,
cross-segment negation, trailing conditions, asset switches, relative pairs,
technical metrics, historical and reported speech, future stance, decimal
timeframes, repeated captions, opposing evidence, exact Unicode offsets, and
forged direction/weight rejection.

Run the focused checks from the repository root:

```bash
python -m unittest tests.test_krown_extract -v
.venv/bin/ruff check signal_lab/krown_extract.py tests/test_krown_extract.py
.venv/bin/mypy signal_lab/krown_extract.py
```

A passing synthetic suite establishes the covered behaviors on the tested
revision. It does not establish recall, precision on all Krown speech, market
profitability, live transcript availability, or execution feasibility. The
runner records the frozen extraction-file hash separately before its holdout
evaluation.

### Observed pre-holdout verification

At extraction SHA-256
`d14bdd6e2cbf1e09541cdbc28d25582a5a5427995548cbf78678099621ae8d62`,
all 27 focused tests passed, Ruff reported no findings, and mypy reported no
issues. The independent reviewer reran its fixed 21 abstention cases across
the three contextual variants: all 63 returned flat. Its two directional
controls across those variants produced all six expected directions. It also
verified decimal-timeframe abstention, identical-caption deduplication, exact
source provenance, and rejection of the demonstrated direction/weight
forgeries. The reviewed file hash was unchanged before and after that run.

The author then ran the final extractor on the twelve development sources,
without prices or returns:

| Variant | Long summaries | Short summaries | Flat summaries | Accepted candidate cues |
|---|---:|---:|---:|---:|
| `lexical` | 10 | 0 | 2 | 339 |
| `context_strict` | 2 | 0 | 10 | 10 |
| `context_standard` | 6 | 0 | 6 | 12 |
| `context_broad` | 8 | 1 | 3 | 25 |

Each variant examined the same 1,864 vocabulary cues. Accepted cues are counted
before clause aggregation, so they are not the number of trades or distinct
forecasts. All retained evidence and cue spans passed exact source validation;
the four variants checked 11,343, 10,769, 11,343, and 11,972 spans respectively.
These are development coverage and provenance results, not a forecast-quality
or trading-performance score.
