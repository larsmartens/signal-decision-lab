# Jev setup

This adapter uses **Jev from TypeSafe**, through the hosted System One API. It has no
local model runtime and does not load weights. The default model is `jev-1.14.0`, which
TypeSafe lists as released on 14 October 2026. The version is pinned so that a replay
experiment does not silently change when a moving alias is updated.

Sources checked on 13 November 2026:

- [Model versions](https://docs.typesafe.ai/models)
- [Choice primitive](https://docs.typesafe.ai/primitives/choice)
- [Confidence definition](https://docs.typesafe.ai/confidence)
- [Official OpenAPI schema](https://api.typesafe.ai/openapi.json)
- [Official Python SDK at f36e685](https://github.com/typesafe-ai/typesafe-sdk-python/tree/f36e68549ceca3191e5791e5f99ea1baa1a258b5)

## Configure and run

The client uses Python's standard library. Set your own TypeSafe key in the shell:

```bash
export TYPESAFE_API_KEY='<your TypeSafe key>'
export TYPESAFE_BASE_URL='https://api.typesafe.ai'
export TYPESAFE_MODEL='jev-1.14.0'
python -m signal_lab demo --judge jev --out artifacts/jev --format json
```

The base URL and model shown above are defaults. `.env.example` documents the variables
but is not loaded automatically. Use a versioned ID if overriding the model; aliases such
as `jev-latest` are rejected. The CLI makes requests only when `--judge jev` is selected
and a reviewed setup passes the deterministic checks.

For your own reviewed input:

```bash
python -m signal_lab replay --signals artifacts/reviewed.json \
  --bars path/to/matching-bars.csv --judge jev \
  --out artifacts/jev-replay.json --report artifacts/jev-replay.html
```

These calls send the signal, its supporting quotes and the current completed price bar
to TypeSafe. The provider's account limits and billing apply. No API key was configured
for this implementation, so live Jev inference remains untested.

## Request and response

The client sends `POST /v1/systemone` with Bearer authentication. Its single Choice question
asks whether the evidence supports the candidate entry at the completed bar close:

```json
{
  "model": "jev-1.14.0",
  "state": {
    "decision_time": "<completed bar close>",
    "signal": "<structured signal and quoted evidence>",
    "completed_bar": "<structured OHLC bar>"
  },
  "questions": {
    "direction": {
      "type": "choice",
      "instructions": "<fixed decision instructions>",
      "criteria": {
        "buy": "The evidence supports this long candidate and its trigger is satisfied.",
        "sell": "The evidence supports this short candidate and its trigger is satisfied.",
        "hold": "The evidence does not support an entry, or its conditions are not satisfied."
      }
    }
  }
}
```

This is a schema illustration: the actual `signal` and `completed_bar` values are objects.
The complete question text and serialization are in [jev.py](../signal_lab/jev.py). No future
bars or realized returns are included. Source quotes are identified as data in the question.
The model is being asked to check evidence and a condition, not to forecast a return.

The response must identify the requested model, contain exactly the requested `direction`
answer, and provide a Choice label, confidence, probabilities and non-negative token counts.
The client rejects missing or duplicate JSON fields, non-finite scores, unknown labels,
invalid probability sums and a selected label below the largest probability. An opposite
direction is also rejected: a long signal cannot authorize a short entry.

## The two scores

TypeSafe defines Choice confidence as a rescaling of the largest probability:

`provider_confidence = (p_max - 1 / n) / (1 - 1 / n)`

For three choices with probabilities `buy=0.8`, `sell=0.1`, `hold=0.1`, the provider's
confidence is `0.7`. Confusing these values would apply a different decision threshold.
The normalized adapter result keeps both:

| Field | Meaning |
|---|---|
| `value` | The selected action: `buy`, `sell` or `hold`. |
| `confidence` | The selected action's probability, used by the replay threshold. |
| `confidence_basis` | `selected_label_probability`. |
| `provider_confidence` | TypeSafe's separate confidence value. |
| `probabilities` | The complete distribution over the three actions. |
| `provider`, `model` | `typesafe` and the exact model version returned. |
| `calibrated` | `false`; this project's inputs have not been evaluated for calibration. |
| `calibration_source` | `provider_claim_not_locally_validated`. |
| `probability_source` | `jev_model` for a validated model answer. |

The default policy requires a selected probability of at least `0.8`. This is an experimental
threshold, not one fitted to a trading validation set. Replay permits the explicitly selected
Jev experiment while preserving `calibrated: false` and the provider provenance. Other
uncalibrated callbacks do not receive that exception. Both scores and the model identity
appear in each valid `model_judgment` event.

The provider's confidence formula is documented but is not independently recomputed as an
acceptance condition. Both values must be finite and within `[0, 1]`; the selected probability
must agree with the selected label. No score is treated as the probability of a profitable trade.

## Failure behavior

A missing key returns a local hold without an HTTP request. HTTP errors, timeouts, redirects,
oversized responses and invalid JSON also produce a hold. The result sets `abstained: true`
and `probability_source: fail_closed_policy`. Its `hold=1` distribution describes the
application's no-entry action; it is not a Jev prediction.

Replay records a bounded error code and discards raw provider error text. It never falls
back to rule-approved trading after a failed Jev call. To run the independent rule baseline,
select `--judge rules` explicitly or omit `--judge`.

When Jev chooses the opposite direction, the audit also retains the validated original
prediction under `model_decision`, including both scores and its probability distribution.
The effective action remains a policy hold. This preserves the rejected prediction for
later error analysis without copying arbitrary provider diagnostics into the run file.

Remote endpoints require HTTPS. HTTP is allowed only for loopback test servers. Redirects
are disabled, keeping evidence and credentials at the configured endpoint. The default
request timeout is ten seconds; the response limit is one MiB.

## What has been tested

[The adapter tests](../tests/test_jev.py) use a real local HTTP server with controlled
responses. They check the official request shape, authentication header, model pin,
score handling, rejection cases and integration with paper replay. These tests exercise
the client and transport; the server does not run Jev.

Run the complete suite:

```bash
python -W error::ResourceWarning -m unittest discover -s tests -v
```

A real provider call, task-specific decision accuracy and calibration remain to be measured.
Use the protocol in [EVALUATION.md](EVALUATION.md) before interpreting acceptance rates or
comparing strategy results.
