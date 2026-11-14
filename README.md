# Signal Decision Lab

Read Krown's market commentary as separate, sourced scenarios: which ticker he means,
what he expects to happen, the conditions for that move, its timeframe, and what would
invalidate it. Keep the passage and its surrounding context attached to the interpretation.

The [latest source reading](docs/research/krown-latest-20261114.md) covers two regular
videos and two completed livestreams available on 14 November 2026. It includes ticker
views, conditional branches, unresolved details and links to the relevant timestamps.
The [claim records](annotations/krown-20261114/claims.json) preserve the structured
interpretations; the [source manifest](datasets/krown-latest-20261114/sources.json)
records the acquisition.

The previous word-based directional analysis, backtest results and charts have been
removed from the current repository. Source metadata and market data remain available
for a future evaluation built on faithful interpretations.

## What the current workflow does

Claims are currently authored by a person or assistant after reading a passage in
context. The code checks their source references, preserves unknown fields, and can
ask **TypeSafe's Jev through OpenRouter** to assess each interpretation. It does not
automatically read and extract every scenario in a full video.

| Part | Current behavior |
| --- | --- |
| Source acquisition | Fetches public channel metadata and timestamped captions; records publication and actual retrieval separately. |
| Contextual claims | Records the subject, expected move, prerequisites, invalidation, timeframe, targets and interpretation author. |
| Evidence checks | Validates exact source references and retains a contiguous passage with surrounding context. |
| Jev review | Asks separate questions about subject, meaning, conditions, invalidation, timeframe, targets and context. |
| Run records | Saves model identity, request hashes, answers, usage, reported cost and failures; resumes completed requests without resending them. |
| Paper mechanics | A separate synthetic demo exercises reviewed setups, fees, risk limits and next-open fills. |

No authenticated Jev call or new semantic backtest has been completed. The current
source interpretations are assistant-authored and are not independent human labels.
See [validation](docs/VALIDATION.md) for the observed tests and remaining gaps.

## Run the offline checks

Use Python 3.11 or later on Linux or macOS. No API key or third-party package is
needed for these commands:

```bash
git clone https://github.com/larsmartens/signal-decision-lab.git
cd signal-decision-lab
python scripts/check_semantic_claims.py \
  --claims examples/semantic-claims.json \
  --transcripts examples/semantic-transcripts
python -m unittest discover -s tests -v
python -m signal_lab demo --out artifacts/demo --format json
```

The semantic example uses synthetic captions. Passing its evidence checks establishes
that the references and input structure are valid; it does not prove an interpretation
is correct. The demo's trade return tests accounting on artificial prices.

## Review the captured claims with Jev

Configure `OPENROUTER_API_KEY` in 1Password and inject it into the process through your
secret-management setup. The application reads the environment variable; it does not
load `.env` files. Keep credentials out of the repository and command arguments.

With the canonical captions available locally:

```bash
python scripts/run_semantic_jev.py \
  --claims annotations/krown-20261114/claims.json \
  --transcripts data/krown-latest/transcripts \
  --out artifacts/jev-semantic \
  --max-requests 8 --cost-stop-usd 1
```

This sends the selected caption passages and proposed interpretations to OpenRouter
and TypeSafe. The runner checks the whole batch before sending requests. Its request
limit applies across resumed runs. The cost setting stops further requests after
reported spend reaches the threshold; use an OpenRouter key limit for a hard billing
ceiling. An uncertain request outcome stops the run rather than retrying automatically.

Jev's answers assess fidelity to the supplied source. Its probabilities do not estimate
trade success. A faithful interpretation can still contain no entry, no target, or no
stated invalidation. [Setup and response contract](docs/JEV_SETUP.md).

Full captions stay in the ignored `data/` directory. Public annotations contain source
references rather than redistributed transcripts. A fresh caption download may differ
from the recorded capture; check its provenance before reusing an annotation.

## Source capture

```bash
python -m pip install -e '.[youtube]'
python scripts/collect_krown.py --help
```

The collector uses Krown's own Videos and Live tabs, validates the channel ID, and
records failed acquisitions. [Corpus notes](docs/research/krown-corpus.md) explain
selection, caption hashes and timestamp semantics.

The existing `extract` command supports a small explicit English setup grammar and
an optional chat-completions adapter. It remains a harness for complete, reviewed
setups; it is not the method used for the current Krown reading. Chart interpretation,
full-video model extraction and automatic conversion of scenarios into orders remain
unimplemented.

## Project notes

- [Implementation plan](docs/PLAN.md): remaining work and its acceptance criteria.
- [Evaluation protocol](docs/EVALUATION.md): source accuracy, Jev checks and a future backtest.
- [Jev research](docs/research/decision-models.md): interfaces, inspected code and papers.
- [Video systems](docs/research/video-signals.md): related implementations and ingestion approaches.
- [Market data](docs/research/market-data.md): retained BTCUSDT candles and provenance.
- [Specification](docs/SPEC.md), [validation](docs/VALIDATION.md) and [review record](docs/REVIEW.md).

There is no broker connection or live order execution.
