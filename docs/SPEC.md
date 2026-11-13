# Signal Decision Lab: prototype specification

Request date: 2026-11-13. Owner: Lars Martens. Repository: private.

## Goal

Research existing Jeff/Jev trading architectures and video/transcript signal extraction.
Deliver an executable, tested research prototype and an evidence-based development plan.
Start with BTCUSDT, explicit English transcript conditions and a single-position paper
simulator. Do not infer a profitable strategy from extraction accuracy or model confidence.

## Required behavior

1. Import timestamped JSON, WebVTT and SRT transcripts with publication AND actual
   availability metadata. Preserve evidence and distinguish commentary, conditional
   setups, explicit instructions, negation and retrospective claims.
2. Extract only supported fields. Unknown stop, target, timeframe or validity horizon
   remains unknown. Reject ungrounded model fields. An explicit reviewer gate precedes
   any paper entry; synthetic fixtures may mark the demo review explicitly.
3. Supply a deterministic baseline, an optional structured LLM extractor, and a
   version-pinned Jeff v1.4 decision client. Model outage, invalid probabilities,
   abstention and missing calibration must produce no model-approved entry.
4. Separate evidence, interpretation, strategy policy, numerical risk and execution.
   Code owns numerical limits. Jeff is an optional rule-interpretation challenger;
   probabilities measure the decision task, not future trading profit.
5. Replay chronologically. Only completed bars and signals available as of decision time
   may be used. Decide at close; earliest fill is next bar open. No future data goes
   to decision callbacks. Fee and adverse slippage apply to both sides; gap stops and
   ambiguous intrabar stop/target order use conservative assumptions. Mark open equity.
6. One position at a time, risk-based size, exposure cap, configurable short simulation,
   drawdown veto, expiring setups, one entry per signal. No broker/exchange order APIs.
7. CLI commands and a self-contained HTML report must make examples, decisions, source
   evidence and blockers inspectable. Offline demo and tests run on Python 3.11+ without
   third-party packages. Optional providers clearly disclose their separate requirements.
8. Ship a current source register, implementation plan, evaluation limitations, CI, setup
   instructions and an exact validation report. Distinguish fake transport tests,
   synthetic scenario tests, genuine source tests and real-model/real-market evaluation.

## Non-goals for this draft

Profit claims; live money; unattended channel scraping; training a Decision Transformer;
complete chart interpretation; portfolio optimization; inference of unspoken price levels.
These are future experiments with explicit acceptance criteria, not hidden defaults.

## Validation acceptance

Offline end-to-end command works. Behavioral tests exercise unknown/negated signals,
evidence spoofing, model failure, no-lookahead, next-open fills, short accounting,
fees, gaps, intrabar ambiguity, stale signals, review gating and size limits.
Public-source examples must never be labeled as manually validated trading signals
unless they are. CI results and actual model invocation status are reported accurately.
