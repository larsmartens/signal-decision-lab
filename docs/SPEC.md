# Specification

Updated 14 November 2026. Repository: [signal-decision-lab](https://github.com/larsmartens/signal-decision-lab/tree/main).

## Goal

Represent the meaning of Krown's statements about individual tickers, including
expected moves, conditions, invalidations and timeframes. Keep the evidence visible
so a reader can check the interpretation before any trading experiment uses it.

## Required behavior

1. Acquire Krown's own regular analysis videos and completed livestreams. Record
   exact source identity, publication metadata, actual retrieval time, caption type
   and content hashes. Preserve incomplete and failed acquisitions explicitly.
2. Represent each subject and scenario separately. Distinguish an asset's price
   from an indicator, a comparison asset or a related instrument. Preserve conditional
   branches, uncertainty, negation and corrections.
3. Record expected movement, prerequisites, invalidation, forecast timeframe and
   target areas only when the source supports them. Unstated fields remain unknown.
   Do not infer an invalidation by reversing a trigger or turn a chart interval into
   a holding period.
4. Separate source evidence from the author's interpretation. Retain timestamped
   segment references and enough continuous context to understand the scenario.
   Record whether an interpretation was written by a human or assistant.
5. Validate evidence before making model requests. Ask Jev narrow fidelity questions
   through a documented provider interface. Pin the model snapshot, preserve usage
   and cost, bound the run, and stop on an uncertain request outcome.
6. Treat model uncertainty and unsupported interpretations as unresolved. A typed
   answer or high confidence does not create missing source facts, an approved
   trading setup or a probability of investment success.
7. Keep trading policy, numerical risk and execution separate from source meaning.
   Future backtests must use explicit availability times, completed bars, eligible
   fills and transaction costs. Researcher-authored rules must be identified.
8. Keep documentation, examples and source references in English and publish changes
   on `main`. Report actual tests, source review, live model calls and backtests
   separately, with reproducible inputs and limitations.

## Current implementation boundary

Contextual claims are authored by reading captions; the software validates and submits
them for optional Jev review. Automatic full-video extraction and chart interpretation
are future work. No authenticated Jev call or new semantic backtest has been completed.

The earlier strict grammar, reviewed `Signal` model and synthetic paper demo remain
available for testing execution mechanics. Semantic claims are not converted into
those signals automatically. The removed word-based video analysis is outside the
current workflow. There is no broker connection or live order execution.

## Acceptance

The offline examples must validate without credentials, and malformed evidence must
fail before a model request. Tests must distinguish real provider results from missing
credentials, local HTTP fixtures and uncertain failures. A source-quality claim needs
independent contextual labels; a trading claim additionally needs a frozen market
evaluation. Detailed criteria belong in [EVALUATION.md](EVALUATION.md).
