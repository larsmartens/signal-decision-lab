# Evaluation protocol

Evaluate whether an interpretation preserves the source's meaning before measuring
anything about trading. A successful HTTP request, a valid schema and a profitable
outcome can all coexist with a false interpretation.

## Current evidence

The [latest reading](research/krown-latest-20261114.md) contains assistant-authored
interpretations of four recent sources. The code validates evidence references and
can submit selected interpretations to Jev. No authenticated Jev call, independent
human labeling study or semantic strategy backtest has been completed.

The former word-based analysis and its result files have been removed. The retained
[source acquisition](../datasets/krown-20261113/sources.json) and
[market candles](../datasets/krown-20261113/market-bars.csv) are inputs for future
research. Existing examined sources are development material, even where their saved
metadata uses an earlier development/holdout split.

Keep five kinds of evidence distinct: source acquisition, contextual reading,
software behavior tests, actual model inference and market evaluation. The
[validation record](VALIDATION.md) states which have been observed.

## 1. Measure interpretation fidelity

Select complete discussion sections before examining later prices. Include statements
about different instruments, conditional branches, retractions and passages that need
an unseen chart. Two readers should annotate independently, then record disagreements
and their resolution. Assistant-authored annotations alone are not a human reference set.

| Dimension | Error to detect |
| --- | --- |
| Subject | Assigning an indicator, comparison asset or related ETF to the wrong ticker. |
| Expected move | Reversing direction, overstating certainty or merging incompatible scenarios. |
| Conditions | Dropping a prerequisite, changing a candle-close condition or missing a branch. |
| Invalidation | Inventing a stop, reversing a trigger or borrowing another scenario's level. |
| Timeframe | Confusing the chart interval with the forecast horizon or supplying an unstated duration. |
| Targets | Treating a current price, prior extreme or indicator value as a stated destination. |
| Context | Resolving pronouns or chart references without enough evidence. |
| Completeness | Missing an expressed scenario while correctly describing the few selected cases. |

Report claim precision and recall as well as field accuracy and unresolved cases.
Measure numbers together with their role and qualifier: an approximate area is not an
exact price, and a conditional target is not an unconditional forecast. Group results
by video; many overlapping snippets from one stream are not independent observations.

An evidence-reference check verifies text identity, offsets and timestamps. It cannot
establish that the passage supports the interpretation. Regression tests should retain
known interpretation failures as cases for subsequent model evaluation, without
pretending that local fixtures measure a model's understanding.

## 2. Evaluate Jev's added value

Freeze the selected claims, complete passages, question text, model snapshot and
acceptance threshold before making the comparison. The current runner asks eight
Choice questions and records `faithful`, `unsupported` or `unclear` per question.
Compare those decisions against the independent labels, including cases where an
incorrect candidate was written fluently and confidently.

Report disagreement detection, missed errors, unnecessary rejection and accepted
coverage. The default selected-answer threshold of 0.8 is an experimental setting;
it has not been calibrated on Krown commentary. Keep the provider's confidence and
choice probabilities separate, following the [TypeSafe definition](https://docs.typesafe.ai/confidence).

For a future calibration study, use held-out labels and report a multiclass Brier
score, reliability plots, bin counts and sensitivity to predeclared binning choices.
[Guo et al.](https://proceedings.mlr.press/v70/guo17a/guo17a.pdf) describe expected
calibration error and its bin-based construction. The existing
[evaluation module](../signal_lab/evaluate.py) supports the older `buy`/`sell`/`hold`
paper harness; it is not yet an evaluator for the new semantic review labels.

Retain API failures, uncertain outcomes, resolved model, request identity, latency,
input/output usage and reported cost. Local HTTP fixtures and cached test replies
must remain identifiable as tests. A missing key is a blocked run, not a model answer.

## 3. Define a separate trading experiment

Only after source review, specify which scenarios can be evaluated under explicit
rules. State how conditions become observable, which instrument and venue are used,
and how entries, exits and conflicting scenarios are handled. If a source omits an
exit or horizon, either leave it outside the executable subset or label the additional
rule as researcher-authored.

Use actual acquisition and interpretation times when available. A retrospective
availability assumption must remain separate from those timestamps. Modern models
may know subsequent events from training; filtering prompt dates cannot eliminate
that risk. Prospective observation is needed to test what the workflow would have
produced as new videos arrived.

Compare reviewed source rules, market-only rules, their combination, and the same
inputs with Jev review. Match sample dates, transaction costs, trade permissions and
risk limits. Include cash, buy-and-hold, exposure and inactivity. Freeze every variant
before opening a fresh test period and record rejected variants too; selecting from
many trials contributes to backtest overfitting ([Bailey et al.](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)).

Report net returns, drawdowns, independent trades, turnover, costs and uncertainty.
Use completed bars and causally available inputs. Describe gaps and ambiguous intrabar
ordering. Derivative claims additionally require funding, borrowing, collateral and
liquidation assumptions. The current semantic workflow has no such result to report.
