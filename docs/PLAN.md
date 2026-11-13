# Implementation plan

Build a record of what Krown said, measure how faithfully the system extracts it, then test whether those statements improve a fixed trading strategy. The [specification](SPEC.md) defines the scope; [EVALUATION.md](EVALUATION.md) defines the measurements. Work targets the repository's [main branch](https://github.com/larsmartens/signal-decision-lab/tree/main).

## Starting point

The prototype imports timestamped transcripts, extracts claims with source evidence, requires review, and replays supported setups against price bars. The default decision rule and all position sizing run in ordinary Python. An optional LLM proposes claims; [TypeSafe's Jev](https://docs.typesafe.ai/introduction) is the intended model for comparing narrowly defined decisions. Jev accepts state and typed questions. Its integration and verification status belong in [JEV_SETUP.md](JEV_SETUP.md).

The code separates [extraction](../signal_lab/extract.py), [LLM proposals](../signal_lab/llm.py), [Jev](../signal_lab/jev.py), [risk](../signal_lab/engine.py), and [replay](../signal_lab/replay.py). Executable setups currently require a limited English grammar. LLM output cannot bypass `unsupported_language`; unsupported corrections, price ranges, and additional conditions remain blocked. Publication times are supplied as metadata and need external verification.

No custom model has been trained, and no Krown trading edge has been established. Live Jev inference has not yet been demonstrated. The stages below describe planned work, with a recorded scope, budget, and acceptance criteria for each experiment.

## 1. Build a Krown corpus with reference labels

Start with a manageable, predetermined sample, such as 30 videos across different market conditions and statement types. That is a workload estimate, not a sample-size justification. Record [Krown's own channel](https://www.youtube.com/channel/UCnwxzpFzZNtLH8NgTeAROFA) separately from guest appearances and identify videos by stable IDs.

For each source, save its URL, publisher, publication time and supporting evidence, actual retrieval time, language, caption type, segment times, content hash, and retrieval tool version. Keep sources with uncertain publication times out of historical performance claims. The [transcript library](https://github.com/jdepoix/youtube-transcript-api) exposes timed snippets and generated-caption status; record failed retrievals too.

Have two people independently label a predetermined subset without seeing later prices. Resolve disagreements and keep the reasons. Labels should cover commentary, conditions, instructions, negation, retrospective statements, uncertainty, and the supporting passages.

**Acceptance:** Every retained claim has traceable source metadata and a reviewed label. Report annotation disagreements and missing data. The [existing interview import](validation/youtube-smoke.json) is a starting point for this work. Human review is likely to dominate the initial cost, so settle the labeling rules before expanding the sample.

## 2. Represent claims faithfully

Give claims their own schema: speaker, instrument, time reference, condition, direction, uncertainty, negation, evidence spans, and unknown fields. Keep executable setups separate. A long-term forecast can be useful even when it has no entry, stop, or expiry.

Test context that crosses caption boundaries. Include number roles, self-corrections, alternative scenarios, and retractions. New executable language patterns need explicit rules and regression cases. [VideoConviction](https://arxiv.org/html/2507.08104v1) documents difficulty distinguishing commentary from recommendations; its stock-video benchmark motivates this test but does not validate crypto extraction.

**Acceptance:** Report field accuracy, evidence accuracy, missed claims, and false executable setups on held-out videos. Fix every known case that creates an unsupported entry before advancing.

Measure text extraction first. Add selected video frames and optical character recognition only when the error analysis identifies missing chart information. Preserve frame time, instrument, scale, and uncertainty. Compare the improvement with the extra inference and review cost. Vision remains planned work.

## 3. Compare the rule baseline, LLM extraction, and Jev

Evaluate LLM claim extraction against the reference labels. Separately, send the same reviewed facts to the deterministic decision rule and Jev. Keep the Jev question narrow enough to have an unambiguous reference answer. Follow [TypeSafe's documented question types](https://docs.typesafe.ai/introduction) rather than carrying over an unrelated model's request format.

Record model identity, request schema, question text, input hash, response, rejection reason, latency, and cost. Test invalid responses and service failures as well as ordinary decisions. Determine confidence thresholds on separate validation data; do not assume the provider's confidence transfers unchanged to this task.

**Acceptance:** Complete a real Jev invocation before claiming model integration. Then report decision accuracy and accepted-decision coverage on the frozen comparison set. Keep the deterministic rule as the default until the comparison supports a useful role for Jev.

Start with a small fixed set. Lowering a threshold after seeing missed entries creates a new variant and requires fresh test data.

## 4. Measure the added value of video claims

Compare three fixed strategies: source claims alone, price rules alone, and their combination. Use the same instruments, dates, execution assumptions, and risk limits. Test Jev as a separate factor. Include fees, slippage, missed entries, and open positions in the results.

Use chronological training, validation, and test windows. Remove examples whose outcome intervals overlap the next partition and set a gap appropriate to the longest outcome horizon. Freeze parameters, model versions, and selection rules before opening each test window. Save a configuration hash and a register of every variant, including rejected ones. Repeated selection on the same data increases backtest overfitting ([Bailey et al.](https://www.davidhbailey.com/dhbpapers/backtest-prob.pdf)).

**Acceptance:** Reproduce the frozen comparisons and explain the uncertainty in any apparent improvement. Add indicators or models only for a stated new hypothesis. Historical LLM experiments also need to account for possible knowledge of later events in model training.

## 5. Run a prospective shadow trial

Process newly acquired sources and record decisions without placing orders. Four to eight weeks is a planning estimate for observing operations. Statistical evidence depends on the number of independent events and market conditions covered.

Keep publication, retrieval, extraction, review, and decision times separate. Version corrections instead of overwriting them. Report outages, rejected claims, manual interventions, model spend, and latency percentiles. A strategy change starts a new evaluation period.

**Acceptance:** Produce a complete record of what was available at each decision and apply the frozen evaluation rules. A low signal count is a result to report, not a reason to relax the source requirements after the fact.

A short source list and daily manual review are sufficient for the first trial. No background jobs are installed by this plan.

## 6. Add an execution framework if the results justify it

Choose a framework once the required venue, instruments, and operating features are clear. Connect through an adapter and begin with its simulated execution mode. Keep sizing and loss limits in the deterministic core.

**Acceptance:** Repeated requests cannot create duplicate orders. Test partial fills, connection loss, restarts, and reconciliation between local and external positions. Each order must trace back to source evidence, a rule version, and a risk decision.

Defer this integration while source quality or incremental trading value remains unresolved. Live deployment is outside the prototype's scope.
