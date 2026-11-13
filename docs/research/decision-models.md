# Using Jev in a system that extracts trading signals

Research updated 13 November 2026.

Jev is a plausible component for checking and classifying claims extracted from trading videos. Its typed questions fit tasks such as identifying a conditional setup, checking whether a quotation supports an extracted field, or deciding which of several candidate price levels the speaker meant. Whether those claims help a trading strategy is a separate question that needs market data and a fixed evaluation policy.

This report uses TypeSafe's official documentation for the product contract, source code for implementation findings, and papers for reported experimental results. The proposed integration below has not been validated as a profitable strategy.

## The current TypeSafe interface

[TypeSafe's introduction](https://docs.typesafe.ai/introduction) describes Jev as its first System One model. A request supplies a shared `state` and named, typed questions. The model evaluates the questions independently against that state. Code combines the answers.

The current model documented on 13 November is **`jev-1.14.0`**, released on 14 October 2026. Both `jev-latest` and `jev-preview` currently point to it. Use the versioned ID for a recorded experiment and retain the returned `model`; aliases can move. TypeSafe documents shared weights across accounts and customization through state, instructions and criteria, rather than customer fine-tuning or LoRA. [Models](https://docs.typesafe.ai/models)

| Interface | What is available |
|---|---|
| HTTP | `POST https://api.typesafe.ai/v1/systemone`, authenticated with a bearer API key. Required fields: `model`, `state`, `questions`. Results are under `answers`, with the responding `model` and token `usage`. |
| Model discovery | `GET /v1/models`. The documented response lists account-visible aliases; versioned model IDs are accepted even when absent from that list. |
| Python | `typesafe-sdk`; synchronous `TypeSafeClient` and asynchronous `AsyncTypeSafeClient`, with `system_one(...)`. |
| JavaScript / TypeScript | `@typesafe-ai/sdk`; `TypeSafeClient.systemOne(...)`. |

Sources: [HTTP reference](https://docs.typesafe.ai/api/system-one), [model discovery](https://docs.typesafe.ai/api/list-models), [Python SDK](https://docs.typesafe.ai/sdk/python), [JavaScript SDK](https://docs.typesafe.ai/sdk/javascript). The official Python docs link to [typesafe-ai/typesafe-sdk-python](https://github.com/typesafe-ai/typesafe-sdk-python). At inspected commit `f36e685`, its [package definition](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f36e68549ceca3191e5791e5f99ea1baa1a258b5/pyproject.toml) specifies version 0.7.5 and Python 3.10 or newer; its [endpoint constant](https://github.com/typesafe-ai/typesafe-sdk-python/blob/f36e68549ceca3191e5791e5f99ea1baa1a258b5/src/typesafe_sdk/_core/constants.py) confirms `/v1/systemone`. The SDK's MIT license applies to the client library; it is not a release of model weights.

| Question | Returned information | Possible use here |
|---|---|---|
| Choice | Selected option, probabilities for every option, and confidence. | Classify a passage as a conditional setup, outlook, historical account, or other statement. |
| Noul | A probability from 0 to 1 that a yes/no statement is true. No separate confidence field. | Check whether the cited passage supports a proposed condition. |
| Score | A position on an ordered rubric, probabilities over its levels, and confidence. | Rate ambiguity using a clearly defined rubric. |
| Box | Image coordinates, with confidence when supplied. Image and Box support is experimental. | Locate a relevant chart region for further inspection. |

These are API primitives, not built-in financial models. Sources: [Choice](https://docs.typesafe.ai/primitives/choice), [Noul](https://docs.typesafe.ai/primitives/noul), [Score](https://docs.typesafe.ai/primitives/score), [Box](https://docs.typesafe.ai/primitives/box).

### Probabilities and confidence

For a Choice with `n` options, TypeSafe defines:

```text
confidence = (highest_probability - 1/n) / (1 - 1/n)
```

For three options, a highest probability of 0.8 therefore gives confidence 0.7. These fields must not be substituted for each other. A threshold on one adds no independent evidence to a threshold on the other when the option count is fixed. Score uses a different formula that accounts for distances between ordered levels. [Confidence documentation](https://docs.typesafe.ai/confidence)

The question determines what a probability refers to. A high probability that a passage describes a long setup does not estimate the chance that a long trade will make money. The HTTP contract also has no `calibrated` or `abstained` flags. Those are application decisions and records; they must not be inferred from a successful response. [API schema](https://api.typesafe.ai/openapi.json)

### Limits that affect video processing

The documented default context limits are 64k tokens per request and 32k for the state plus any individual question. An experimental header raises both to 262k, with an explicit accuracy and latency caveat. Jev accepts text and PNG/JPEG images; it does not natively accept audio or video. Image requests require the `TypeSafe-Danger-Zone-Images: true` header. Captions, speech recognition and frame selection remain separate ingestion steps. [Models](https://docs.typesafe.ai/models), [image support](https://docs.typesafe.ai/images)

TypeSafe identifies weaknesses in arithmetic, numeric precision, date comparison, long irrelevant context, indirection, adversarial input and option ordering. It recommends extracting candidate values with code or a generative model, then asking Jev to select among them. That fits a transcript pipeline: preserve exact source spans and let code handle prices, timestamps and risk calculations. Typed output does not establish that the selected answer is correct. [Known model limitations](https://docs.typesafe.ai/model-jaggedness)

Requests also have a 32 MiB body limit and require finite JSON numbers. Rate limits are account-specific; overload and rate-limit responses need bounded retries. A replay or live observer should record these failures and wait rather than silently manufacture a model answer. [Request rules and errors](https://docs.typesafe.ai/api/errors)

## A concrete trading implementation: buberlo/jev-trader

The closest inspected Jev-specific example is [buberlo/jev-trader](https://github.com/buberlo/jev-trader), at commit [`15d089e656d968fabb750bde8ebeec6d0da1ac7d`](https://github.com/buberlo/jev-trader/commit/15d089e656d968fabb750bde8ebeec6d0da1ac7d), dated 19 September 2026. This is a third-party market-making prototype. It does not ingest videos.

Its [question battery](https://github.com/buberlo/jev-trader/blob/15d089e656d968fabb750bde8ebeec6d0da1ac7d/src/jev_trader/judgment/battery.py) asks for regime, short-horizon direction, toxic flow, liquidity stress, quoting conditions and inventory pressure. The [policy engine](https://github.com/buberlo/jev-trader/blob/15d089e656d968fabb750bde8ebeec6d0da1ac7d/src/jev_trader/policy/engine.py) converts these outputs into quoting actions. Separate [risk checks](https://github.com/buberlo/jev-trader/blob/15d089e656d968fabb750bde8ebeec6d0da1ac7d/src/jev_trader/risk/limits.py) can hold, reduce exposure or kill the loop. Pricing and execution are separate modules.

Those boundaries are useful to borrow. The inspected implementation also has limits that matter when reading its results:

- The [paper command](https://github.com/buberlo/jev-trader/blob/15d089e656d968fabb750bde8ebeec6d0da1ac7d/src/jev_trader/cli.py) always uses synthetic market data and a simulated venue. An API key enables actual Jev judgments within that simulation; it does not make the market data real.
- Without a key, the command selects a heuristic judge. On an API exception, the [loop](https://github.com/buberlo/jev-trader/blob/15d089e656d968fabb750bde8ebeec6d0da1ac7d/src/jev_trader/loop/engine.py) also falls back to heuristics. A timeout instead produces a hold. Counts distinguish these paths.
- The [calibration loader](https://github.com/buberlo/jev-trader/blob/15d089e656d968fabb750bde8ebeec6d0da1ac7d/src/jev_trader/calibration/metrics.py) drops neutral outcomes but retains the original three-way probability of “up.” That changes the population being evaluated without conditioning the probability on it.
- The calibration command defaults to mixing judgment sources. It fits Platt scaling and reports the resulting Brier score on the same samples. That is a fit diagnostic, not evidence of calibration on unseen data.

The source was inspected without installing or executing this repository. Its latency statements and simulated results were not reproduced. Use it as an example of module responsibilities; build and evaluate the transcript-specific questions separately.

## What the papers support

### Independent Jev evaluation

Deußer, Sparrenberg and Sifa's September 2026 preprint, [Evaluating and Benchmarking the System One Model Jev](https://arxiv.org/html/2609.37647v1), evaluates **`jev-1.13.0`** on 37 datasets. It reports pooled Choice ECE of 0.028, but results vary substantially by task. Financial PhraseBank reaches 73.0% accuracy with ECE 0.138. Binary and multilabel Noul tasks often need task-specific thresholds; fitting those on separate training examples improves some results.

The study includes [evaluation code and recorded responses](https://github.com/AppliedMachineLearning-Lab/jev-benchmarking). It measures language tasks, not trading returns. It uses one frozen template per dataset, runs each request once, and cannot rule out training exposure to benchmark questions. Its findings justify testing Jev as a classifier or evidence checker, with fresh channel-specific labels. They do not establish performance for version 1.14, crypto forecasts or Krown transcripts.

### Evidence on typed decision models

Tang and Zheng's [Typed Decision Models: An Early Evidence Audit and Evaluation Checklist](https://arxiv.org/html/2609.32160v1) reviews 28 early papers. It finds useful efficiency results but no established accuracy advantage attributable to the typed interface itself. Calibration and deferral thresholds depend on the workload. The review covers a short September 2026 release window and largely preprint evidence.

For this project, the practical comparison is Jev against a simple extractor, an ordinary model with constrained labels, and human-reviewed claims. Report the fraction of cases accepted as well as their error rate. A system can look accurate by refusing nearly everything.

### Learning a trading policy from trajectories

[Decision Transformer](https://arxiv.org/abs/2106.01345) conditions actions on desired return, past states and actions. The [authors' implementation](https://github.com/kzl/decision-transformer) is a starting point for that form of offline reinforcement learning. Yun's [2024 trading study](https://arxiv.org/abs/2411.17900), with [replication code](https://github.com/syyunn/finrl-dt), adapts GPT-2 with LoRA and compares it with other offline RL methods.

This would require a different training dataset: market states, available signals, actions, costs and subsequent outcomes. A transcript archive alone does not supply those trajectories. Jev's hosted question API offers a more direct first experiment for semantic interpretation; a learned policy can be evaluated later if the recorded data supports it.

## Proposed integration

Keep the [timestamped extraction contract](video-signals.md#recommended-extraction-contract) as the common input. Use short passages with their exact quotes, candidate fields and source times. Ask separate questions whose errors can be labeled:

| Question | Suggested primitive | What code does afterward |
|---|---|---|
| What kind of statement is this? | Choice, including historical, hypothetical and unclear options. | Keep statements outside the supported setup classes out of the execution path. |
| Does the passage support this specific condition? | Noul, one check per condition. | Flag disagreement or uncertainty for review. |
| Which observed number is the stop or invalidation? | Choice over source candidates, including “not stated.” | Preserve the chosen span and parse the exact number. |
| Which stated scenario does this passage describe? | Choice over explicit branches, including “none.” | Evaluate that scenario’s numeric conditions against closed market bars. |
| Does the evidence leave a material ambiguity? | Noul or a narrow ambiguity rubric. | Keep the candidate pending when the meaning is unresolved. |

These questions are proposed experiments. They should not be described as implemented capabilities merely because Jev can accept their schema.

After interpretation, code checks source availability, review status, expiry, instrument, timeframe, trigger and the complete entry/stop/target bracket. Position sizing, costs, exposure and drawdown limits remain deterministic. A model answer can withhold an otherwise eligible paper trade; it cannot make an expired or incomplete setup eligible.

Start by recording Jev's answers alongside the baseline without changing its trades. Label extraction errors and measure calibration on later examples. Then freeze the questions, thresholds and policy and compare the baseline with the model-filtered replay on a later period. Keep API failures, abstentions, latency and actual model IDs in the record. Measure the effect of adding Jev separately from the effect of adding video information.

No authenticated Jev inference was performed for this report. Live latency, channel-specific accuracy and incremental trading value remain unmeasured here. HTTP fixtures can verify request and error handling; they cannot supply that evidence.

## Historical correction

An earlier revision investigated the unrelated `firelex/jeff` project after misreading the intended model name. That research and its local inference results remain in [commit `f883ace`](https://github.com/larsmartens/signal-decision-lab/blob/f883ace43922c73bffb553fc3aed7a89e7b4562f/docs/research/decision-models.md). They are not evidence about TypeSafe's Jev.

