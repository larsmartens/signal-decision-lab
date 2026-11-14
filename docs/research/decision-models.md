# Jev for contextual source review

Updated 14 November 2026. Jev can answer narrow questions about a proposed reading of
a trading passage: whether the ticker is the actual subject, whether a condition was
preserved, or whether an invalidation is stated. Its role in this project is to check
authored interpretations against their source context.

The [current workflow](../../README.md) contains a typed claim model, evidence
validation and a bounded OpenRouter runner. No authenticated Jev inference or semantic
strategy backtest has been completed. The current source readings were authored by
an assistant; they are not independent human reference labels.

## OpenRouter access and model identity

[OpenRouter's Jev guide](https://openrouter.ai/docs/guides/community/jev) documents
access with an ordinary OpenRouter API key, without a separate TypeSafe account.
The [decision-model catalog](https://openrouter.ai/api/v1/models?output_modalities=decisions)
identifies `typesafe/jev-1.14` and canonical snapshot `typesafe/jev-1.14-20261014`.
The [model page](https://openrouter.ai/typesafe/jev-1.14) lists a 262,144-token context
and $0.042 per million input tokens, with free output tokens, as checked on this date.

| Interface | Contract |
| --- | --- |
| OpenRouter Decisions | `POST https://openrouter.ai/api/alpha/decisions`; `state`, `questions`, `model`; OpenRouter bearer key. |
| OpenRouter System One | `POST https://openrouter.ai/api/v1/systemone`; compatibility route for the TypeSafe SDK. |
| Direct TypeSafe | `POST https://api.typesafe.ai/v1/systemone`; separate TypeSafe key and version naming, such as `jev-1.14.0`. |

Sources: [Decisions reference](https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request),
[TypeSafe SDK through OpenRouter](https://openrouter.ai/docs/guides/community/typesafe-sdk),
[direct TypeSafe API](https://docs.typesafe.ai/api/system-one).
The project uses the first route for semantic review. The earlier direct-TypeSafe
adapter remains part of the synthetic paper harness. [Setup details](../JEV_SETUP.md).

## What typed decisions provide

Jev accepts shared application state and named questions. The API supports Choice,
Noul, Score and Box primitives. Choice selects among described options and returns
probabilities; Noul answers a binary proposition; Score uses an ordered rubric; Box
locates an image region. The current project client implements Choice. Jev does not
generate a free-form explanation or a complete transcript-derived scenario.
[OpenRouter primitive overview](https://openrouter.ai/docs/guides/community/jev).

The semantic runner asks eight checks: subject, expected move, stance, conditions,
invalidation, timeframe, targets and context. Each offers `faithful`, `unsupported`
and `unclear`. A human or assistant first supplies the candidate and its evidence.
A future generative extractor can supply the same schema, but that extraction stage
has not been implemented for full Krown videos.

Choice probabilities and provider confidence have different meanings. For `n` choices,
TypeSafe defines confidence as `(highest_probability - 1/n) / (1 - 1/n)`.
Thus a maximum probability of 0.8 across three choices produces confidence 0.7.
The question defines what that probability concerns; source fidelity is not a trading
win probability. [Confidence documentation](https://docs.typesafe.ai/confidence).

TypeSafe documents weaknesses in arithmetic, numeric precision, long irrelevant
context, indirection and adversarial input. Keep numerical calculations in ordinary
code and preserve exact source evidence for interpretation. A typed answer still
requires evaluation against labeled examples.
[Model limitations](https://docs.typesafe.ai/model-jaggedness).

## Inspected Jev trading implementation

[buberlo/jev-trader](https://github.com/buberlo/jev-trader), inspected at commit
[`15d089e`](https://github.com/buberlo/jev-trader/commit/15d089e656d968fabb750bde8ebeec6d0da1ac7d),
is a market-making prototype. Its
[question battery](https://github.com/buberlo/jev-trader/blob/15d089e656d968fabb750bde8ebeec6d0da1ac7d/src/jev_trader/judgment/battery.py)
asks about regime, direction, liquidity and inventory. Separate
[policy](https://github.com/buberlo/jev-trader/blob/15d089e656d968fabb750bde8ebeec6d0da1ac7d/src/jev_trader/policy/engine.py)
and [risk](https://github.com/buberlo/jev-trader/blob/15d089e656d968fabb750bde8ebeec6d0da1ac7d/src/jev_trader/risk/limits.py)
modules control actions. It does not ingest videos.

The inspected [paper command](https://github.com/buberlo/jev-trader/blob/15d089e656d968fabb750bde8ebeec6d0da1ac7d/src/jev_trader/cli.py)
uses synthetic market data and a simulated venue, even when a key enables real Jev
judgments. Its [loop](https://github.com/buberlo/jev-trader/blob/15d089e656d968fabb750bde8ebeec6d0da1ac7d/src/jev_trader/loop/engine.py)
can fall back to heuristics after API exceptions. Its
[calibration code](https://github.com/buberlo/jev-trader/blob/15d089e656d968fabb750bde8ebeec6d0da1ac7d/src/jev_trader/calibration/metrics.py)
drops neutral outcomes and fits and reports calibration on the same samples by default.
Those results cannot establish calibration on new source material. The repository
was inspected, not executed; no latency or performance claim was reproduced.

## Relevant papers

### Jev evaluation

[Evaluating and Benchmarking the System One Model Jev](https://arxiv.org/html/2609.37647v1)
by Deußer, Sparrenberg and Sifa evaluates `jev-1.13.0` on 37 datasets. It reports pooled
Choice ECE of 0.028, with substantial task differences; Financial PhraseBank reaches
73.0% accuracy and ECE 0.138. The
[evaluation repository](https://github.com/AppliedMachineLearning-Lab/jev-benchmarking)
contains code and recorded responses. These are language-task measurements for a
different model version. They do not establish performance on Krown commentary or
trading returns.

### Typed interfaces and evaluation

Tang and Zheng's [Typed Decision Models: An Early Evidence Audit and Evaluation Checklist](https://arxiv.org/html/2609.32160v1)
reviews 28 early papers. It finds efficiency evidence but no established accuracy
advantage attributable to the typed interface alone. The project therefore needs
source-specific reference labels and a comparison with an ordinary model using
constrained answers. Report accepted coverage and missed errors alongside accuracy.

### Learning a policy from trajectories

[Decision Transformer](https://arxiv.org/abs/2106.01345) conditions actions on desired
returns, previous states and actions; the [authors' implementation](https://github.com/kzl/decision-transformer)
is available. Yun's [2024 trading study](https://arxiv.org/abs/2411.17900), with
[replication code](https://github.com/syyunn/finrl-dt), adapts GPT-2 with LoRA for offline
reinforcement learning. That approach needs trajectories containing market states,
actions, costs and outcomes. A caption archive alone does not provide this training set.

## Next experiment

Run the small fixed claim batch after secure credential setup, retain every result,
and compare Jev's checks with independent contextual labels. The request record must
preserve model identity, source hashes, selected passages, questions, latency, usage,
cost and failures. A changed prompt or threshold starts a new experiment.

Only after interpretation quality is measured should reviewed scenarios enter a
separate trading policy. Conditions and invalidations stay attached to their subject;
position sizing, price comparisons and risk limits remain deterministic. See the
[evaluation protocol](../EVALUATION.md) for the source and market evidence required.

## Name correction

An earlier revision investigated the unrelated `firelex/jeff` project after misreading
the intended name. The intended model is **Jev from TypeSafe**. Results from that other
model provide no evidence about this integration.
