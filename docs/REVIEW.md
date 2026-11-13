# Historical software review

Recorded on 13 November 2026, before the model identity was corrected from firelex/Jeff to TypeSafe's Jev. This review record appeared in [commit f883ace](https://github.com/larsmartens/signal-decision-lab/tree/f883ace43922c73bffb553fc3aed7a89e7b4562f). Model-specific findings below concern the former Jeff integration. They provide no evidence about Jev.

Two separate reviewers checked the implementation against the specification and coding standards. They started from the first local specification commit and then retested the reported findings. Current validation results belong in [VALIDATION.md](VALIDATION.md).

## Coding standards

| Finding | Original severity | Resolution recorded at the time |
|---|---|---|
| Unchecked statistics could inject HTML into the report | P1 | Restricted statistics to nonnegative integers and escaped output. A malicious-bundle test confirmed that invalid input produced no report file. |
| Reviewing a signal overwrote its original extraction time | P2 | Added separate `extracted_at` and `reviewed_at` fields. Decision availability remained the latest required timestamp. |
| A Jeff abstention appeared in the audit as a malformed response | P2 | Handled the exact policy-fallback form separately and preserved the bounded reason code and probability source. This fix applied to the old Jeff adapter. |

The standards reviewer confirmed all three fixes with three targeted regression tests and reported no further material design findings within that review's scope.

## Specification

| Finding | Original severity | Resolution recorded at the time |
|---|---|---|
| A drawdown alarm closed a position at the just-observed closing price | P1 | Deferred the risk exit to the next observed open. Gap and end-of-data regression tests passed. |
| The consolidated validation report was missing | P2 | Added `docs/VALIDATION.md`, separating evidence types and listing uncompleted checks. |
| The CPU test description said four threads while measurements reported eight | P3 | Documented four requested threads and eight reported after loading; preserved the raw measurements. These were tests of firelex/Jeff. |

The specification reviewer confirmed the execution fix and corrected thread description. The missing validation report was added afterward. All six reported findings were addressed; P1 was the highest original severity. This was a software review, with no strategy-performance audit.

## Jev integration review, 13 November 2026

A reviewer who did not write the revised implementation checked the working tree against
`f883ace43922c73bffb553fc3aed7a89e7b4562f`. The review covered the Jev adapter, CLI selection,
replay gate, and report changes, using TypeSafe's [OpenAPI contract](https://api.typesafe.ai/openapi.json)
and [confidence definition](https://docs.typesafe.ai/confidence).

The request uses the pinned model and Choice question format. The client preserves the
selected probability separately from provider confidence. Replay records `calibrated: false`
and the provider's unvalidated calibration claim. Jev requires explicit selection; the default
remains the deterministic rule. Model approval cannot override source eligibility or risk checks.

Two audit defects were fixed and verified:

| Finding | Severity | Verified resolution |
|---|---|---|
| An oversized provider score from an abstaining custom callback could raise an overflow error during audit construction | P2 | `_jev_experiment` checks bounds before converting the score for a finiteness check. The replay rejects the entry and omits the invalid score. |
| Replay discarded the valid model prediction when the adapter rejected its direction | P2 | `_rejected_jev_evidence` validates and retains a fixed set of fields under `model_decision`, separately from the effective policy hold. Invalid nested evidence and raw diagnostics are excluded. |

The fixes are in [replay.py](../signal_lab/replay.py), with regression cases in
[test_replay.py](../tests/test_replay.py). Focused runs passed 19 adapter tests, 38 replay
tests, and nine CLI tests. Commands:

```bash
python -W error::ResourceWarning -m unittest discover -s tests -p 'test_jev.py' -v
python -W error::ResourceWarning -m unittest discover -s tests -p 'test_replay.py' -v
python -W error::ResourceWarning -m unittest discover -s tests -p 'test_cli.py' -v
```

An independent local HTTP probe returned a valid `sell` answer for a long candidate. Replay
made no entry, retained the model's `sell=0.9` distribution and `provider_confidence=0.85`,
and kept a future signal out of the request. A separate oversized-score probe completed
without an exception and produced finite JSON. The rule demo made one synthetic entry;
the Jev demo with no key made none and recorded `missing_api_key`.

No unresolved behavioral findings remain in the reviewed scope. These checks used controlled
local responses; they did not call hosted Jev or measure its decision quality or calibration.
