# Validation record

Updated 14 November 2026 (study data cut off at November 13, 23:00 UTC). This record separates software tests, real source acquisition
and model inference. The project has not established a profitable trading strategy.

## Current checks

The latest local counts and tool output are saved in
[offline-tests.json](validation/offline-tests.json). The suite covers the default offline
pipeline, local HTTP provider fixtures, source grounding, time ordering and paper accounting.
It runs with resource warnings treated as errors.

| Check | Result | What it establishes |
|---|---|---|
| Behavioral tests | 232 passed, no failures, errors or skips on Python 3.12.14 | Behavior on specified cases; no estimate of extraction accuracy on a Krown corpus. |
| Ruff and Mypy | Passed; 16 source modules checked | Lint and type checks on the maintained implementation. |
| Offline demo | Six synthetic claims, one reviewed setup, one completed paper trade | The pipeline runs and records its evidence and execution assumptions. |
| Jev HTTP contract | Local server tests exercise real HTTP requests and controlled responses | Client behavior against the published contract, including distinct probability and confidence fields. |
| Jev live inference | Not run; no TypeSafe API key was configured | No claims about live responses, latency, calibration or trading value. |
| Own-channel acquisition | 36/36 selected videos and completed streams; 66,992 caption segments | Verified source identity, metadata, retrieval and hashes; no audio verification. |
| Literal setup coverage | 1,950 asset mentions and zero complete supported setups across the 36 sources | Coverage of the limited grammar, not proof that the source contains no actionable views. |
| Directional experiment | 24 strategy runs and 12 distinct controls on actual BTCUSDT candles | Reproducible fixed-rule historical calculations, not validated source interpretation. |
| Independent accounting audit | 36 result blocks, 284 completed trades and 28,638 hourly equity points reconciled | Quantities, costs, P&L, exposure, drawdown and all controls independently recomputed. |
| Post-outcome semantic audit | Both profitable strict-rule holdout outputs failed source-context review | Known subject and condition errors; selected cases cannot estimate corpus-wide accuracy. |
| Study figures | Four PNG/SVG pairs generated with Matplotlib and visually checked | Counts, loss signs, axes, controls, costs and semantic-audit note are visible. |
| Independent review | Findings and verification are recorded in [REVIEW.md](REVIEW.md) | Targeted checks by a reviewer who did not write the revised implementation. |

[GitHub Actions](https://github.com/larsmartens/signal-decision-lab/actions) runs the suite,
Ruff, Mypy, the demo and exact offline reproduction of the Krown study on Python 3.11 and 3.13. The workflow definition is not evidence of a
successful run; use the check attached to the commit being assessed.

## Behaviors covered

- Negated, retrospective, illustrative and ambiguously attributed statements remain blocked.
  Extra conditions that the execution schema cannot represent also prevent approval.
- Stops, targets and trigger levels must match their roles in the quoted source. A number
  appearing elsewhere in the transcript is insufficient. Ranges and corrections are not
  silently reduced to one value.
- Review repeats the executable-language checks. Removing an `issues` field from a model's
  proposal cannot make unsupported text executable.
- Publication, retrieval, extraction, review and decision availability remain separate.
  A late import or review cannot extend the original expiry.
- Subtitle comments are excluded from speech. Malformed timestamps cause an error rather
  than silently dropping potentially relevant wording.
- Model callbacks receive one completed bar and an already available, immutable signal.
  Entries wait for the next contiguous open. Fees and adverse slippage apply on both sides.
- A gap can cause a loss larger than the planned stop risk. Ambiguous intrabar stop/target
  collisions use the stop first; a target already reached at the open has known precedence.
- Drawdown exits wait for the next observed open. A regression case enters 100 units at 100,
  observes a drawdown at a close of 90 and exits at the next open of 70, realizing a loss of
  3,000. If the data end at the alert, the position remains open and marked to market.
- Jev's selected probability and provider confidence remain distinct. The paper experiment
  records its unvalidated calibration status and cannot override source or risk checks.
- Missing credentials and provider failures prevent entry. An application-generated hold
  is labeled as policy output and cannot be mistaken for a model probability.
- Source text is escaped in HTML. Report statistics containing executable markup are rejected.

## Real source acquisition

The [channel study](experiments/krown-20261114/README.md) now uses 18 normal videos and
18 completed streams from `@ECKrown`, with twelve development sources and 24 holdout
sources. Its [validation receipt](../experiments/krown-20261114/validation.json) records
the performed checks. Source selection, numeric policy and extractor code were frozen
before empirical returns. The later context review is explicitly post-outcome and leaves
the frozen results intact. Its failure prevents treating those labels as reviewed entries.

The following earlier interview acquisition remains a separate smoke test.

[youtube-smoke.json](validation/youtube-smoke.json) records the actual retrieval time,
language, caption hash and processing result for the
[Cointelegraph interview with Eric Krown](https://www.youtube.com/watch?v=EdXslFg3u38).
The video's YouTube microformat reported `publishDate` and `uploadDate` as
`2026-09-02T08:01:27-07:00`, equivalent to **2 September 2026, 15:01:27 UTC**.
The acquisition happened on 13 November, so this record does not claim the source was
observed in September.

The audio was not independently checked and the captions were not manually labeled.
The full third-party transcript remains outside git. A short attributed sentence is used
only as a negative test for an ambiguous forecast.

## Correction to the earlier model research

An earlier version tested `firelex/jeff` after the intended model name was misidentified.
Those CPU runs concern a different model. They do not validate Jev and are no longer part
of the active setup or current test record. The
[previous validation record](https://github.com/larsmartens/signal-decision-lab/blob/f883ace43922c73bffb553fc3aed7a89e7b4562f/docs/VALIDATION.md)
and its raw measurements remain in git history.

The current adapter follows TypeSafe's official API and pins `jev-1.14.0`. Its contract,
configuration and limits are documented in [JEV_SETUP.md](JEV_SETUP.md).

## Remaining gaps

Generative extraction has transport and schema tests, but no external LLM call was completed.
The optional CPU transcription adapter has not been exercised with an actual Whisper model.
Chart reading and OCR are not implemented.

HTML generation, escaping and report data have been tested. Visual desktop and mobile
review was not completed: local Chromium could not start under the environment's socket
restriction, and the separate cloud browser could not reach the local server. The responsive
CSS is therefore present but not visually verified.

That limitation concerns the earlier HTML replay report. The new Matplotlib study charts
were rendered and directly inspected as images.

The new historical experiment is a directional heuristic with known semantic errors;
there is still no labeled reconstruction of Krown's strategy, prospective performance sample
or measured trading advantage. The simulator has no broker connection, funding or borrow costs,
order-book liquidity model or margin liquidation model. Short positions are optional simulations.

The next measurements and acceptance criteria are in [PLAN.md](PLAN.md) and
[EVALUATION.md](EVALUATION.md).
