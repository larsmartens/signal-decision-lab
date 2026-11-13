# Prototype specification

Requested on 13 November 2026 by Lars Martens. Repository: [signal-decision-lab](https://github.com/larsmartens/signal-decision-lab/tree/main).

## Goal

Build a tested research prototype for extracting claims from trading videos and evaluating them under explicit trading rules. Start with BTCUSDT, English transcript conditions, and a simulator that holds one position at a time. Compare a deterministic baseline with optional LLM extraction and Jev from TypeSafe. Extraction accuracy and model confidence must be evaluated separately from trading returns.

## Required behavior

1. Import timestamped JSON, WebVTT, and SRT transcripts with publication and actual availability metadata. Preserve source evidence and distinguish commentary, conditional setups, instructions, negation, and retrospective claims.
2. Extract only supported fields. Leave unstated stops, targets, candle intervals, and validity horizons unknown. Reject fields that the cited evidence does not support. Require explicit review before a paper entry; synthetic demo fixtures must identify their review as synthetic.
3. Provide a deterministic baseline, an optional structured LLM extractor, and an optional Jev client using [TypeSafe's documented interface](https://docs.typesafe.ai/). Record the model identity and request format used. Service failures, malformed answers, and abstentions must produce no model-approved entry. Validate any returned probability distribution before using it; evaluate decision thresholds on the project's own labeled data.
4. Keep source evidence, interpretation, strategy policy, numerical risk, and execution separate. Code controls numerical limits. Jev may judge a narrow decision question; it cannot supply missing source facts or override risk limits. Its current setup and verification status belong in [JEV_SETUP.md](JEV_SETUP.md).
5. Replay in chronological order. Use only completed bars and signals available at decision time. Decide at close and fill no earlier than the next eligible open. Do not pass future data to decision callbacks. Charge fees and adverse slippage on entry and exit. Use conservative gap-stop and intrabar-ordering assumptions, and mark open positions to market.
6. Hold at most one position. Apply risk-based sizing, an exposure cap, an optional short-simulation setting, a drawdown veto, setup expiry, and one entry per signal. The prototype has no broker or exchange order integration.
7. Provide CLI commands and a self-contained HTML report that expose examples, decisions, evidence, and blockers. The offline demo and behavior tests must run on Python 3.11 or later without third-party packages. Document optional providers' additional requirements.
8. Maintain source references, a development plan, evaluation criteria, CI, setup instructions, and an accurate validation record. Distinguish controlled HTTP tests, synthetic scenarios, genuine source retrieval, real model calls, and market evaluation.

## Scope limits

The prototype does not train a Decision Transformer, interpret complete charts, optimize a portfolio, infer unspoken price levels, scrape channels unattended, or place live orders. Follow-up work and its acceptance criteria belong in [PLAN.md](PLAN.md).

## Acceptance

The offline workflow must run end to end. Behavioral tests must cover unknown and negated signals, forged evidence, model failure, future-data leakage, next-open fills, short accounting, fees, gaps, intrabar ambiguity, expired signals, review requirements, and size limits.

Public-source examples must state whether anyone checked them against the recording or labeled their trading meaning. Report actual CI results and model-call status. Historical tests of firelex/Jeff are not Jev validation.
