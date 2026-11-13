# Evaluation protocol

## Completed channel study

The [November 2026 experiment](experiments/krown-20261114/README.md) applies a fixed
12-source development / 24-source holdout split to Krown's own regular videos and
completed streams. It publishes all 24 strategy runs, matched controls, source references
and charts. The [protocol](../experiments/krown-20261114/PROTOCOL.md) records its actual
execution assumptions. A post-outcome source audit rejected both profitable strict-rule
interpretations. This is a reproducible negative research result; a blind labeled
extraction benchmark and a prospective performance trial remain outstanding.

Use this protocol for the experiments in [PLAN.md](PLAN.md). Record metrics and acceptance thresholds before opening the test data. Changing a threshold after reading the results creates a new hypothesis.

## What has been demonstrated

The [recorded import](validation/youtube-smoke.json) of the [Cointelegraph interview with Krown](https://www.youtube.com/watch?v=EdXslFg3u38) retrieved 646 automatically generated English caption segments. The YouTube page gives both publication and upload as 2 September 2026 at 15:01:27 UTC. Retrieval took place on 13 November, so the application cannot claim to have observed these captions in September.

The baseline produced 46 unreviewed claims classified as commentary and no complete supported setups. This confirms ingestion and records the baseline's output. It does not measure extraction accuracy. The captions have not been independently checked against the audio.

The intended decision model is Jev from TypeSafe. Live inference through the corrected Jev integration has not yet been demonstrated. An earlier revision tested the unrelated firelex/Jeff model; those eight CPU calls are documented in [the historical validation record](https://github.com/larsmartens/signal-decision-lab/blob/f883ace43922c73bffb553fc3aed7a89e7b4562f/docs/VALIDATION.md). They provide no evidence about Jev. Use [JEV_SETUP.md](JEV_SETUP.md) and [VALIDATION.md](VALIDATION.md) for the current integration status and test results.

Keep evidence categories separate: synthetic behavior tests, controlled HTTP responses, real model calls, source retrieval, and trading experiments. No custom Decision Transformer or validated Krown trading edge exists in this project.

## Measure source understanding

Create reference labels before examining later prices. Put videos about the same event and overlapping excerpts in the same data partition. Keep test videos closed while changing prompts, grammar, or schemas. Include usable claims, incomplete forecasts, and difficult negative examples.

Report the following for each extractor:

- Claim precision and recall, broken down by statement type and instrument.
- Field accuracy for both a number and its role: entry, target, stop, horizon, or candle interval. Unstated values should remain absent.
- Evidence accuracy, including negation, hypothetical conditions, retrospective statements, corrections, and speaker attribution.
- False executable setups and coverage of genuinely executable reference cases, alongside the number and reasons for abstentions.

Aggregate results by video and report uncertainty. Many segments from one video are not independent observations. Give each known false-entry failure a behavioral regression test. Overall accuracy can conceal poor extraction when most statements are commentary.

## Measure decision accuracy and calibration

The current evaluation target is the action `buy`, `sell`, or `hold` under a specified rule. A correct rule decision is distinct from a profitable trade. Record prediction and label-observation times. The [evaluation module](../signal_lab/evaluate.py) computes accuracy, coverage, expected calibration error (ECE), and a multiclass Brier score.

The Brier score averages the sum of `(p − y)²` across all three classes, with `y = 1` for the correct class and zero otherwise. This implementation does not divide the sum by three; its range is zero to two. It measures the quality of the full probability distribution, not calibration alone.

ECE groups the highest class probability into equal-width bins, then weights the absolute difference between average confidence and observed accuracy by each bin's size. This follows the approach described by [Guo et al.](https://proceedings.mlr.press/v70/guo17a/guo17a.pdf). ECE depends on the grouping and sample. Report a reliability plot, bin counts, class counts, a confusion matrix, and sensitivity to predetermined binning choices. Ten bins is an implementation default.

The current accuracy calculation includes abstained rows. Also report accuracy among accepted decisions against their coverage. Fit thresholds and any calibration adjustment on training or validation data only. Keep application-generated fallback distributions out of model-quality results. Interpret Jev's confidence according to its [documented meaning](https://docs.typesafe.ai/confidence); do not assume it equals the maximum class probability. Neither ECE nor Brier measures trading returns.

## Preserve the information available at each decision

A setup becomes usable only after its source is available and extraction and review have completed. Late ingestion must not extend its original expiry. Label historical reconstructions as reconstructions when no contemporaneous acquisition record exists.

In walk-forward evaluation, choose a strategy using earlier data and evaluate it unchanged in the next time window. Remove training examples whose outcome intervals reach into validation or test periods. Set the gap between partitions from outcome horizons and publication delays. Fit preprocessing and thresholds within the training period too.

Modern LLMs may know later events from their training data. Filtering the supplied prompt by date cannot remove that knowledge. A prospective trial therefore provides evidence that historical replay cannot supply.

## Compare the same trading problem

| Variant | Information used for signals | Purpose |
|---|---|---|
| Source | Reviewed claims and their stated triggers | Measure the source's contribution |
| Price | Predetermined rules on past prices | Establish a baseline without creator input |
| Combined | Source and price rules | Measure the source's added value |
| Each variant with Jev | The same facts, with an additional model decision | Measure model benefit and cost |

Every variant needs prices for triggers, risk checks, and fills. The source-only variant gets no extra technical indicators. Keep trade permissions, costs, risk budgets, and dates comparable. Log every variant tested: selecting the best of many backtests is itself a source of overfitting ([Bailey et al.](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)).

## Report financial and operational results

Report net return, maximum drawdown, marked-to-market equity, exposure, turnover, independent trades, and costs. Include cash and buy-and-hold over the same dates. Vary fees and slippage. Before making claims about derivatives, account for funding, borrowing, liquidity, and liquidation; the current simulator does not model these fully.

Decisions use completed bars. Entry can occur no earlier than the next eligible open. Keep conservative assumptions for ambiguous intrabar ordering. Use time blocks when estimating uncertainty, and explain sparse samples and dependence on market conditions. Strategy selection stays frozen after the test is opened.

The report should also record retrieval failures, review effort, model spend, and latency percentiles. Attach the dataset version, code commit, configuration, exclusions, and unresolved limitations so another researcher can reproduce the experiment.
