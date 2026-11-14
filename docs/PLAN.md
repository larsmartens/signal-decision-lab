# Implementation plan

The next useful result is a faithful record of what Krown says about each instrument:
the expected move, its prerequisites, the relevant timeframe, and the circumstances
that would invalidate it. A direction assigned to an entire video cannot preserve
that meaning when the speaker discusses several assets or alternative scenarios.

Work targets the public [main branch](https://github.com/larsmartens/signal-decision-lab/tree/main).

## Current state

The word-based directional pipeline and its result files have been removed. The
[latest reading](research/krown-latest-20261114.md) records contextual interpretations
from four recent own-channel sources. The code validates their evidence and provides
a bounded Jev review runner through OpenRouter. Source acquisition and historical
BTCUSDT candles are retained under `datasets/`.

The current claims were authored after reading captions. They are not automatically
extracted, independently human-labeled or checked against every video frame. No
authenticated Jev invocation or semantic strategy backtest has been completed.

## 1. Check source meaning

Use one claim per subject and scenario. Read enough surrounding discussion to resolve
pronouns, comparison assets, self-corrections and conditional branches. Preserve the
speaker's uncertainty. Keep the chart interval distinct from the forecast horizon,
and keep an invalidation distinct from an entry trigger or a protective stop.

Have a second reader assess a predetermined sample without seeing later prices.
Record disagreements and the passages that resolve them. Check the recording when
captions leave a ticker, level or chart reference uncertain.

**Acceptance:** each retained field has source evidence; missing information stays
unknown; independent review measures both omissions and unsupported additions.
The [evaluation protocol](EVALUATION.md) defines the dimensions to report.

## 2. Run Jev on those interpretations

Use the [OpenRouter setup](JEV_SETUP.md) with the API key injected from 1Password.
Keep a fixed model snapshot, questions, selected passages and probability threshold.
Start with the saved small batch and retain every answer, failure and usage receipt.

**Acceptance:** demonstrate an actual provider response with its resolved model and
reported cost, then compare Jev's fidelity decisions with independent reference labels.
HTTP fixtures establish client behavior but cannot satisfy this model-quality check.

## 3. Add automatic candidate extraction

Use a generative model to propose structured scenarios from complete discussion
sections. Preserve all supporting spans and link revisions of the same scenario.
Jev can check those proposals using the same contract as the authored claims.
Neither stage should invent unstated targets, horizons or invalidations.

**Acceptance:** measure claim precision and recall on new videos, including missed
conditional branches and wrong-subject errors. Report the full acquisition and
extraction workload, request counts and cost. Evaluate chart frames only where the
text leaves an identified gap.

## 4. Backtest explicit scenarios

Define the executable subset after source review. Specify how each condition becomes
observable, when an entry could occur, and how ambiguous or unstated exits are handled.
Any researcher-authored trading rule must be labeled separately from Krown's statement.
Acquire matching market data for each instrument and venue.

**Acceptance:** freeze selection and execution rules before inspecting a new outcome
period; compare source, market-only and combined strategies under matching costs and
risk. Include failures, inactivity, exposure and uncertainty. The already inspected
sources are development material and cannot supply a new blind holdout.

## 5. Observe new publications prospectively

Record actual retrieval, interpretation and decision times as new videos arrive.
Start with manual review and paper records. Version changed views instead of replacing
earlier statements, and report missed acquisitions and unresolved contexts.

**Acceptance:** produce an auditable record of decisions made with information available
at that time. A change to extraction or execution starts a new evaluation period.
No background collection or live trading service is installed by this plan.
