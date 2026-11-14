# Contextual Krown annotations

`claims.json` contains eight assistant-authored scenarios from the latest source reading.
It records what the speaker means about a ticker, including pending conditions,
invalidation, timeframes, targets and uncertainty. It contains no Jev answers or trades.

The examples were selected after reading the sources for interpretation difficulties:
BTC's separate horizons, TSLA's support and reversal levels, HYPE's pending close,
RDW's timeframe correction, CRSP's conditional range and XMR's subject attribution.
This is a diagnostic set. It cannot estimate extraction accuracy on unseen videos.

Each field retains a paraphrase and exact caption references. Character offsets and
SHA256 hashes identify the cited text without redistributing it. The manifest also pins
the canonical source captures. The matching raw transcripts remain outside Git.

Validate the original captures locally:

```bash
python scripts/check_semantic_claims.py \
  --claims annotations/krown-20261114/claims.json \
  --transcripts data/krown-latest/transcripts
```

The captured `available_at` timestamp is part of the source identity. A fresh download
is a new capture; the checker rejects it if it differs. Do not backdate a fresh capture
to force a hash match. The committed [synthetic example](../../examples/semantic-claims.json)
and its transcript provide a reproducible offline path without third-party captions.

After configuring the OpenRouter credential through the intended secret manager, use
the bounded command in [Jev setup](../../docs/JEV_SETUP.md). Every claim is preflighted
before requests begin. A model-supported verdict assesses the interpretation of the
supplied passage; it does not approve a trade or establish that the complete video
contains no relevant qualification elsewhere.

The [source reading](../../docs/research/krown-latest-20261114.md) covers more tickers than
these eight examples. The [source manifest](../../datasets/krown-latest-20261114/sources.json)
records which videos were selected and when they were acquired.
