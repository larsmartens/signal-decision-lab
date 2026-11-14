# Jev through OpenRouter

Use this page to validate contextual claims locally and submit a bounded batch to
TypeSafe's Jev through OpenRouter. The current integration has passed controlled
HTTP tests. An authenticated provider call has not yet been completed.

## Provider contract

The [OpenRouter Jev guide](https://openrouter.ai/docs/guides/community/jev) documents
access with an OpenRouter API key. Jev accepts state and typed questions, and returns
answers with probabilities. It does not generate the prose interpretation stored
in a claim. A person or assistant supplies that interpretation first.

| Setting | Pinned value |
| --- | --- |
| Endpoint | `POST https://openrouter.ai/api/alpha/decisions` |
| Request model | `typesafe/jev-1.14` |
| Expected resolved model | `typesafe/jev-1.14-20261014` |
| Provider | TypeSafe |
| Credential variable | `OPENROUTER_API_KEY` |
| Supported question type in this client | Choice |

The [Decisions API reference](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request)
documents the request and response. The [decision-model catalog](https://openrouter.ai/api/v1/models?output_modalities=decisions)
identifies the canonical snapshot. The default model catalog filters for text output;
use the `output_modalities=decisions` query when checking Jev's availability.

## Prepare the source records

Validate the supplied synthetic example without credentials:

```bash
python scripts/check_semantic_claims.py \
  --claims examples/semantic-claims.json \
  --transcripts examples/semantic-transcripts
```

For the real captured annotations, substitute:

```bash
python scripts/check_semantic_claims.py \
  --claims annotations/krown-20261114/claims.json \
  --transcripts data/krown-latest/transcripts
```

The real command needs the exact canonical captions from the recorded acquisition.
The public manifest stores source identities, hashes, segment references and character
offsets. The loader reconstructs the evidence from those local captions and rejects a
mismatched capture. A new download is a new acquisition, even if its words look similar.
Full captions are not committed.

Validation checks the input schema, exact evidence, source identity and complete
request size. It makes no model call and does not certify the interpretation's meaning.

## Configure the credential and run

Store the OpenRouter key as `OPENROUTER_API_KEY` in your 1Password environment and inject
it into the process using your configured secret-management integration. The program
reads that environment variable directly. It does not load `.env`, write a key file
or accept the key as a command argument. The 1Password connection must be available
before this setup can be completed; it was unavailable in the implementation session.

```bash
python scripts/run_semantic_jev.py \
  --claims annotations/krown-20261114/claims.json \
  --transcripts data/krown-latest/transcripts \
  --out artifacts/jev-semantic \
  --max-requests 8 --cost-stop-usd 1
```

The runner requires Python 3.11 or later on a Unix system for its process lock. It
sends the selected passages, surrounding captions and authored interpretations to
OpenRouter and TypeSafe. No market prices, subsequent returns or trading orders are
part of this review.

`--max-requests` caps reserved requests across the saved run, including a restart.
`--cost-stop-usd` stops further calls after observed spend reaches the threshold.
The request that reaches it can exceed it, so use a provider-side key limit for a
hard dollar ceiling. Reported costs are retained; an unknown cost stops the run.
There is no automatic retry after an uncertain network outcome.

The [model page](https://openrouter.ai/typesafe/jev-1.14), checked on 14 November 2026,
lists $0.042 per million input tokens and free output tokens. Use actual `usage.cost`
from each response when reporting a run. Request byte counts are not token or billing
estimates.

## How the questions are used

The fixed questions check subject, expected move, stance, conditions, invalidation,
timeframe, targets and sufficient context. Each answer is `faithful`, `unsupported`
or `unclear`. Null fields mean the selected passage does not state that information;
they do not assert that it is absent from the entire video.

The runner reports `model_supported` only when every check selects `faithful` at or
above the fixed selected-probability threshold. A sufficiently confident unsupported
answer produces `model_disagreed`; unresolved or low-probability answers produce
`uncertain`. The default threshold is 0.8 and has not been calibrated on this task.

A Choice answer includes both class probabilities and a provider confidence value.
[TypeSafe's confidence formula](https://docs.typesafe.ai/confidence) rescales the largest
probability relative to a uniform distribution. With three choices, a maximum
probability of 0.8 corresponds to confidence 0.7. The runner thresholds the selected
probability and retains both fields. Neither value measures the chance of a trade
making money.

## Request records and failure behavior

The runner validates every prepared request before sending the first one. The client
limits the complete UTF-8 payload to 32,768 bytes by default, including the question
text. The selected context has a separate limit. Oversized context must be reviewed
and split into coherent scenarios; it is not silently truncated.

The saved protocol fixes source and request hashes, model identities, questions,
thresholds and run limits. Endpoint and transport distinguish OpenRouter inference
from loopback HTTP tests. Completed matching receipts are reused. Changed inputs or
configuration require a new output directory, and an interrupted in-flight receipt
requires investigation before any retry.

The client validates the exact model snapshot, provider, answer and choice sets,
probabilities, request ID, token usage and cost. Invalid responses contain no invented
semantic answers. Missing credentials stop the command. Provider errors and timeouts
are recorded without copying raw response text or authorization headers into output.
Redirects are refused. The default socket timeout is 30 seconds and the response limit
is one MiB.

## Separate direct-TypeSafe paper adapter

The original [paper adapter](../signal_lab/jev.py) remains available through
`python -m signal_lab demo --judge jev`. It expects `TYPESAFE_API_KEY`, calls
`https://api.typesafe.ai/v1/systemone` and uses `jev-1.14.0`. It judges an eligible
reviewed setup in the synthetic execution harness. The OpenRouter semantic command
above is the path for the new caption-interpretation review.
