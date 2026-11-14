# Validation record

Updated 14 November 2026. The current work checks whether a recorded interpretation
preserves what a speaker said about an instrument, its conditions and its invalidation.
Software correctness, source interpretation and trading performance need different evidence.

## What was checked

The [test receipt](validation/offline-tests.json) records the actual commands and results
on the revised source. [GitHub Actions](https://github.com/larsmartens/signal-decision-lab/actions)
runs the suite, lint, types and offline examples on Python 3.11 and 3.13. Check the run
attached to the commit being assessed.

| Check | Evidence | Limit |
|---|---|---|
| Latest source acquisition | Four original-channel caption tracks, 6,187 segments; metadata and hashes in the [source manifest](../datasets/krown-latest-20261114/sources.json) | Current automatic captions; audio and chart frames were not inspected. |
| Contextual reading | Full reading of both daily videos and both selected streams by the authoring assistant | An assistant interpretation, without independent human reference labels. |
| Independent contextual review | A second assistant read the full latest stream, both daily videos and six older ticker passages; all 275 evidence references in eight annotations matched the captions | Targeted review, not corpus-wide accuracy or a blind evaluation. |
| Public annotation replay | Reference-only manifests hydrate against exact canonical transcripts and reject changed content | A hash proves identity, not semantic truth. |
| OpenRouter client | Actual local HTTP tests check requests, model identity, typed answers, usage, errors and redirect refusal | The fixture server does not run Jev. |
| Semantic runner | Whole-batch preflight, immutable protocol, bounded requests, cached costs and interrupted-request handling | The observed-cost stop is not a hard account billing limit. |
| Synthetic paper mechanics | The separate demo makes one reviewed synthetic trade with recorded costs and timing | It does not evaluate Krown's views. |

The [context review receipt](validation/semantic-context-review.json) states exactly which
sources and passages the non-author reviewer read. The [latest reading](research/krown-latest-20261114.md)
keeps older statements dated separately, preserves conflicting levels and leaves absent
invalidations unknown.

## Live model status

No authenticated OpenRouter/Jev request has been completed. The Google sign-in was not
completed, and an active 1Password connection was unavailable. No API key was created,
stored in 1Password or committed. Missing credentials produce an explicit error and no
model result. Local HTTP fixtures and contextual assistant reviews are labeled separately.

The configured model request is `typesafe/jev-1.14`; the required resolved identity is
`typesafe/jev-1.14-20261014`. A valid future response must retain its provider, request ID,
input/output tokens and reported cost. See [Jev setup](JEV_SETUP.md).

## Removed analysis

The word-based Krown classifiers, video-level direction scores, fixed-hold backtests,
result files and performance charts have been removed from the current repository.
Those interpretations failed to preserve asset identity and conditional meaning. The
source acquisition records and market candles remain under [datasets](../datasets).
They do not establish a trading result.

The older exact-grammar setup parser remains only as a separate executable-setup harness.
Its tests check evidence roles, negation, review and execution mechanics. It is not used
to produce the current Krown reading or the semantic annotations.

## Remaining work

Jev's semantic fidelity, calibration and incremental value have not been measured. The
eight selected annotations are diagnostic examples, including a previously examined XMR
case. They are not an unseen benchmark. A wider evaluation needs independent reference
labels, full source coverage and explicit treatment of chart-dependent statements.

A new backtest must use the actual conditions and horizons in the source. It must keep
unresolved ticker identities, conflicting levels and incomplete execution instructions
out of automatic trades. No new backtest or live order was run for this revision.
