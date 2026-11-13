# Extracting trading information from YouTube

Research updated 13 November 2026. This review covers creator identity, a real transcript, public implementations, extraction quality, and the work needed to evaluate a trading edge. The four repositories below were inspected without installing or running them. Their performance figures are the authors’ reported results and were not reproduced here.

## Main finding

Extracting useful, reviewable trading information from videos is feasible. Several small repositories implement much of the ingestion and rule-extraction workflow. None of the inspected evidence establishes that automatically trading Eric Crown/Krown’s videos produces a profitable strategy after costs. The strongest directly relevant research is useful principally as an extraction benchmark. A defensible prototype should first create a timestamped record of conditional claims, then evaluate those claims separately from any trading policy.

## Creator identity and a real transcript

The verified YouTube channel is currently **Krown**, handle **[@ECKrown](https://www.youtube.com/@ECKrown)**, channel ID **UCnwxzpFzZNtLH8NgTeAROFA**. Its description links the Krown teaching site, which identifies its founder as **Eric Crown** and associates its audience with ECKrown. The teaching site describes an educational process and explicitly excludes copy-trading signals. These links establish the creator’s identity; they do not verify performance claims. Sources: [YouTube channel](https://www.youtube.com/channel/UCnwxzpFzZNtLH8NgTeAROFA), [Krown site](https://krown-trading.teachable.com/), [first-party course page](https://krown-trading.teachable.com/p/kulti).

### Historical extraction example, not a current recommendation

Cointelegraph’s own [episode page](https://cointelegraph.com/podcasts/proof-of-thesis/bitcoin-likely-to-4x-in-the-next-2-years-erik-crown-breaks-down-the-data-proof-of-thesis) embeds [YouTube video EdXslFg3u38](https://www.youtube.com/watch?v=EdXslFg3u38). Its [publisher-hosted Buzzsprout transcript](https://www.buzzsprout.com/2646521/episodes/19753958-bitcoin-likely-to-4x-in-the-next-2-years-erik-crown-breaks-down-the-data-proof-of-thesis?t=0) provides speaker timestamps. Cointelegraph dates the episode September 2, 2026; Buzzsprout dates it September 4. These publisher-page dates remain different; the original YouTube timestamp was subsequently verified, as recorded in the dated correction below.

| Source interval | Faithful extraction | What must remain unresolved |
|---|---|---|
| 2:36–4:28 | BTC long-term investment thesis; historical drawdown/forward-return discussion; spot exposure, explicitly “doing things on spot, not on leverage.” | No executable entry, position size, or stop in this passage. Historical statistics are the speaker’s claims. |
| 4:38–8:43 | Separate conditional September/October/Q4 scenarios; positive September close conditions the October projection. | Do not activate a conditional projection immediately. Targets have different horizons. |
| Same 4:38–8:43 block | Speaker corrects a prior weekly high from 82,000 to 82,800; distinguishes touching six figures from ending the year there. | Retain the correction and distinguish barrier-touch from terminal-price outcomes. |

The transcript contains transcription errors. This review used the publisher’s text; numeric values still need checking against the recording before use. The passages above also show why a single bullish/bearish label would lose conditions that matter to a trade.

## Closest public implementations

### 1. mostlyerror/yt-trade-distill

[Repository](https://github.com/mostlyerror/yt-trade-distill). Inspected head: `a374bc2615aed85c05e0d1050547fa74aedeb431`, last commit June 15, 2026. A compact Python pipeline enumerates a channel, downloads captions through yt-dlp, maps videos into structured rules, reduces them into a canonical specification, and generates Pine Script plus a Python backtest. It is the most directly useful source of a structured strategy-extraction design among the inspected projects. [README](https://github.com/mostlyerror/yt-trade-distill/blob/a374bc2615aed85c05e0d1050547fa74aedeb431/README.md)

**Verified implementation details:**

- [`ingest.py`](https://github.com/mostlyerror/yt-trade-distill/blob/a374bc2615aed85c05e0d1050547fa74aedeb431/yt_trade_distill/ingest.py) records video ID, title and upload date, caches captions, and skips missing captions. [`transcript.py`](https://github.com/mostlyerror/yt-trade-distill/blob/a374bc2615aed85c05e0d1050547fa74aedeb431/yt_trade_distill/transcript.py) removes cue timestamps. The source video survives; precise evidence times do not survive into cleaned text.
- [`prompts.py`](https://github.com/mostlyerror/yt-trade-distill/blob/a374bc2615aed85c05e0d1050547fa74aedeb431/yt_trade_distill/prompts.py) asks for short evidence excerpts, confidence, mechanical predicates, content classification, contradictions and source video IDs. Missing order-flow thresholds can remain null. However, the same prompt defaults an unspecified swing lookback to five bars. That is an implementation assumption, despite the broader instruction against invented numbers.
- [`distill.py`](https://github.com/mostlyerror/yt-trade-distill/blob/a374bc2615aed85c05e0d1050547fa74aedeb431/yt_trade_distill/distill.py) implements parallel extraction and hierarchical reduction. Code joins the video provenance metadata. The evidence excerpts are model output; the inspected path does not check that every extracted claim and number follows from its cited text.
- Reduction favors more recent rules. **Inference:** backtesting a specification built from an entire channel against earlier dates introduces hindsight unless the input videos are restricted to the information available at each historical decision date.

**Backtest limitations visible in code:** [`generate_backtest.py`](https://github.com/mostlyerror/yt-trade-distill/blob/a374bc2615aed85c05e0d1050547fa74aedeb431/yt_trade_distill/generate_backtest.py) substitutes a 2% stop when no mechanical stop exists, hardcodes 1% equity risk and a five-basis-point commission per side, and enters at the same closing price used to compute the signal. Its equity curve updates on realized P&L and omits open-position mark-to-market losses. An open final position is not force-closed for the reported realized return. These choices can change both strategy meaning and reported drawdown; they require replacement or explicit modeling before meaningful evaluation.

The extraction and code-generation pipeline is worth studying. The inspected material contains no independently audited profitability result, and the backtest needs the corrections above before its results can support an evaluation.

### 2. jackson-video-resources/yt-strategy-agent

[Repository](https://github.com/jackson-video-resources/yt-strategy-agent). Inspected head: `b88f977ae7904268c4c3eda0fd93351f7492ad7d`, April 29, 2026. Its Python pipeline monitors a creator over time: recent videos become rules, risk/timing notes, self-reported executed trades and a strategy-change log. [README](https://github.com/jackson-video-resources/yt-strategy-agent/blob/b88f977ae7904268c4c3eda0fd93351f7492ad7d/README.md)

[`extract.py`](https://github.com/jackson-video-resources/yt-strategy-agent/blob/b88f977ae7904268c4c3eda0fd93351f7492ad7d/extract.py) calls an LLM and parses JSON containing buy/sell rules, evidence snippets, risk notes, timing notes and purported executed trades. Its confidence definition measures how emphatically the host states a rule. That is neither the probability the extraction is correct nor the probability a trade wins. The source schema has no timestamp span or typed conditional/negation fields. [`transcript.py`](https://github.com/jackson-video-resources/yt-strategy-agent/blob/b88f977ae7904268c4c3eda0fd93351f7492ad7d/transcript.py) requests Apify transcripts as a single text string, losing cue-level timing in its interface.

[`weighting.py`](https://github.com/jackson-video-resources/yt-strategy-agent/blob/b88f977ae7904268c4c3eda0fd93351f7492ad7d/weighting.py) groups semantically similar rules with sentence embeddings and a 0.82 cosine threshold. Actual effective confidence is a weighted mean divided by total weight. Thus a rule appearing only in the oldest video can retain its original confidence; its confidence does not decay simply because it is old. This differs from the README’s simpler description. Semantic similarity also cannot, on its own, establish that two conditions or negations have the same trading meaning.

Adapting this monitoring pipeline would require a different confidence definition, retained timestamps and separate records for conditional scenarios. Its extraction accuracy and trading value remain unestablished.

### 3. CO0Oper/quant-intern

[Repository](https://github.com/CO0Oper/quant-intern). Inspected head: `2e55261740239ebd086e9a5a00a9d3c229e516f4`, June 5, 2026. The author labels this a hackathon demonstration. Its supported path uses a CLI agent plus a TradingView MCP connection to extract rules, generate/compile Pine, and compare a ticker/timeframe matrix with buy-and-hold. The README reports two tested strategy types and a sample in which only one of nine cells beats its own buy-and-hold comparison. Those are self-reported demo results. [README](https://github.com/CO0Oper/quant-intern/blob/2e55261740239ebd086e9a5a00a9d3c229e516f4/README.md)

Actual [`src/transcript_fetch.js`](https://github.com/CO0Oper/quant-intern/blob/2e55261740239ebd086e9a5a00a9d3c229e516f4/src/transcript_fetch.js) only reads an explicitly provided or cached transcript; it throws when neither exists. A standalone Node invocation does not independently deliver the advertised end-to-end flow. [`TECHNICAL.md`](https://github.com/CO0Oper/quant-intern/blob/2e55261740239ebd086e9a5a00a9d3c229e516f4/TECHNICAL.md) explains the dependency on agent-operated TradingView tools and a known-good fallback script.

The [`resolver` prompt](https://github.com/CO0Oper/quant-intern/blob/2e55261740239ebd086e9a5a00a9d3c229e516f4/prompts/resolver.md) explicitly converts vague language into conventional numeric defaults and logs assumptions. The [`extractor` prompt](https://github.com/CO0Oper/quant-intern/blob/2e55261740239ebd086e9a5a00a9d3c229e516f4/prompts/extractor.md) defaults unspecified symbol/timeframe to gold/one hour absent a supplied hint. [`spec_schema.js`](https://github.com/CO0Oper/quant-intern/blob/2e55261740239ebd086e9a5a00a9d3c229e516f4/src/spec_schema.js) checks shape/types; it does not verify source fidelity.

This demonstrates how a proposed strategy can become an inspectable experiment. Any performance result belongs to the strategy after interpretation and added defaults. Attributing it to the video creator would require showing that those choices preserve the original instructions; a fallback strategy needs its own result label.

### 4. tonbistudio/model-trader

[Repository](https://github.com/tonbistudio/model-trader). Inspected head: `a069235251f0e640362e08ecc2fd647f4fbf75f5`, April 17, 2026; one commit at inspection. It has transcript ingestion, LLM strategy/philosophy drafting, pattern detectors, gate/scanner interfaces, a paper trader and backtest scaffold. A Hyperliquid executor also exists in the source tree. The user still has to translate the drafted strategy into scanner gates. [README](https://github.com/tonbistudio/model-trader/blob/a069235251f0e640362e08ecc2fd647f4fbf75f5/README.md)

[`fetch_youtube_transcripts.py`](https://github.com/tonbistudio/model-trader/blob/a069235251f0e640362e08ecc2fd647f4fbf75f5/pipeline/fetch_youtube_transcripts.py) strips timestamps and produces running text. [`extract_strategy.py`](https://github.com/tonbistudio/model-trader/blob/a069235251f0e640362e08ecc2fd647f4fbf75f5/pipeline/extract_strategy.py) asks for triggers, timeframes, stops, targets, exceptions and contradictory statements, then drafts a first-person trading persona. The outputs are prose, not a validated event schema. A generated persona adds no evidence that the system reproduces the trader’s judgment.

**Concrete backtest defect:** [`docs/backtest.md`](https://github.com/tonbistudio/model-trader/blob/a069235251f0e640362e08ecc2fd647f4fbf75f5/docs/backtest.md) says historical data has already been truncated to the simulated timestamp. In the inspected [`runner.py`](https://github.com/tonbistudio/model-trader/blob/a069235251f0e640362e08ecc2fd647f4fbf75f5/model_trader/backtest/runner.py), the full `hist` and `corr_hist` dictionaries are passed unchanged to the scanner. No truncation occurs in that runner. A scanner written to trust the documentation can see future candles. The runner also calculates outcomes in gross risk units without fee, slippage, funding or borrow-cost deductions.

The backtest mismatch needs correction and tests of information availability before the results can be used.

## Research evidence and adjacent frameworks

### VideoConviction, KDD 2025

The [paper](https://arxiv.org/html/2507.08104v1) studies 288 U.S.-stock videos, 687 recommendation segments and 6,063 expert annotations. Best reported segmented F1: ticker 86.23%; ticker plus action 54.28%; ticker/action/conviction 28.17%. These evaluate 2025-era models, not every model available in November 2026. Crypto is outside this dataset’s intended stock focus. Segment timestamps and negative examples are valuable for evaluation.

Portfolio results use **human labels**, not the model predictions, with six-month holds. Reported annual returns: following buys 9.74%, SPY 11.28%, QQQ 17.55%, inverse 17.90%. Inverse Sharpe is 0.41 versus SPY 0.65. Excluding stocks below $5 changes inverse annual return to −20.97%; this is material sensitivity, not a general recommendation to short creators. These reported experiments do not validate Krown or an automated extraction-to-trading pipeline. [Methods, Table 7 and Appendix J](https://arxiv.org/html/2507.08104v1)

[Code](https://github.com/gtfintechlab/VideoConviction) and [dataset](https://huggingface.co/datasets/gtfintechlab/VideoConviction) are public. The repository’s [LICENSE.md](https://github.com/gtfintechlab/VideoConviction/blob/master/LICENSE.md) says CC BY-NC 4.0 while its README describes the dataset as CC BY-NC-SA 4.0. For commercial reuse, resolve the exact applicable terms; public availability is not an unrestricted commercial grant.

### Additional finfluencer evidence

Aaron J. Black’s March 2026 working paper, [YouTube Finfluencers and Retail Investor Stock Trading](https://papers.ssrn.com/sol3/Delivery.cfm/6451318.pdf?abstractid=6451318&mirid=1), reports LLM extraction of stock mentions and bullish/neutral/bearish stances. Its abstract describes modest short-run returns without longer-horizon abnormal performance and increased retail buying after mentions. **Only the indexed primary-source abstract was accessible** in this session; I did not verify the full methodology, model accuracy, cost assumptions or replication materials. Treat it as corroboration that this research task exists, not as a validated blueprint.

### TradingAgents and FinGPT

[TradingAgents](https://github.com/TauricResearch/TradingAgents) is an adjacent multi-agent financial-analysis framework. Current documentation covers fundamental, news, sentiment, technical and risk roles, and records repeated 2026 fixes to point-in-time data/backtesting. Its social analyst is described around news, StockTwits and Reddit. The inspected project overview does not establish a ready-made Krown/video extraction pipeline. **Inference:** it could consume validated video claim records as an additional input, but adopting its agents would not replace the source-extraction and evaluation work.

[FinGPT](https://github.com/AI4Finance-Foundation/FinGPT) supplies financial language-model, sentiment, instruction-tuning and forecasting components. Its Forecaster is described as trained on U.S. Dow 30 data. It can provide a baseline model/toolkit; that does not establish capability to recover conditional crypto trade setups from charts and speech. These broad frameworks should be evaluated against a simple structured extractor before adding orchestration complexity.

## Ingestion components and multimedia constraints

| Component | Confirmed capability | Engineering implication |
|---|---|---|
| [YouTube Data API captions.download](https://developers.google.com/youtube/data/reference/rest/v3/captions/download) | Requires authorization and permission to edit the video. | Do not assume an ordinary API key grants official transcript downloads for arbitrary channels. |
| [youtube-transcript-api](https://github.com/jdepoix/youtube-transcript-api) | Exposes text, start time, duration, language and generated/manual status; documents cloud-IP blocking. | Retain the structured snippets and source type. Retrieval failure needs its own state; it is not “no trading view.” |
| [yt-dlp](https://github.com/yt-dlp/yt-dlp) | Subtitle/auto-caption and media acquisition tooling used in inspected pipelines. | Preserve original VTT and metadata before normalization. Retrieval remains a separate dependency from extraction. |
| [WhisperX](https://github.com/m-bain/whisperX) | Speech recognition, forced word alignment and speaker diarization; documents imperfect overlap/diarization and some numeric tokens without alignment. | Useful fallback for permitted media. Validate prices and speaker attribution, and do not manufacture exact timestamps where alignment is missing. |

**Design recommendation, not a benchmark result:** start with transcript extraction, then request a few source frames around claims containing chart references or missing numeric levels. OCR can recover a price label or timeframe, but a chart label is not automatically an entry instruction. Preserve the frame timestamp, visible symbol/exchange/timeframe, text bounding box and uncertainty. Resolve phrases such as “this level” using the nearby frame and audio together. If they conflict, retain both observations and abstain until reviewed. Raw video should be a targeted evidence channel rather than a reason to discard readable transcripts.

## Recommended extraction contract

The following design addresses the observed failure modes. It can serve either a conventional extractor or the [proposed Jev integration](decision-models.md#proposed-integration); the inspected repositories do not already provide the complete contract.

| Field group | Required semantics |
|---|---|
| Identity/provenance | Channel ID, video ID, original URL, source time interval, speaker, transcript type/version/hash, optional frame references. |
| Information availability | Original published timestamp, first observation timestamp, transcript available timestamp, extraction completion timestamp. Keep missing values unknown. |
| Claim type | Explicit trade instruction, conditional setup, market outlook, historical trade, educational example, quotation of another person, advertisement, retraction. |
| Instrument | Asset, venue, pair, spot/perpetual/options and direction. Ambiguity is explicit. |
| Preconditions | Typed conditions with comparator, threshold, timeframe and touch-versus-close semantics; conjunctions/disjunctions retained. |
| Entry/exit/risk | Entry trigger/zone, targets, stop/invalidation, expiry and sizing when stated. Every numeric field points to evidence; unstated values remain null. |
| Temporal scope | Distinguish chart candle timeframe, forecast horizon, intended holding period and signal expiry. |
| Interpretation | Negation, hypothetical status, alternatives and corrections; avoid combining mutually exclusive scenarios into one order. |
| Confidence | Keep extraction confidence, transcription confidence and the speaker’s claimed probability separate. None automatically measures expected trading success. |
| Lifecycle | Candidate → waiting for condition → active → expired/invalidated/superseded; preserve the prior version. |

The extractor should be permitted to return no actionable setup. A bullish outlook is still valuable research data, but a deterministic trading policy must define independently whether and how it can cause an order. Missing source details should not silently become conventional stop distances, leverage or target levels.

## Evaluation and protection against hindsight

1. **Evaluate extraction before returns.** Annotate a channel-specific sample with independent human review. Include multiple assets, intraday versus multi-year horizons, corrections, negations, adverts, historical trades, hypothetical illustrations and two-way scenarios. Score action/condition/price/horizon/invalidation fields separately. Track false actionable signals and abstention coverage; a superficially valid JSON object is not a correct signal.
2. **Verify every actionable claim against evidence.** Check exact quoted text exists at the source span; separately test whether it entails the extracted condition. Validate number normalization, units, operator direction and speaker. Schema validation alone cannot do this.
3. **Freeze source vintages.** For a historical decision, include only videos and revisions available before that decision. Never distill a creator’s entire current archive and pretend the resulting rules were known years earlier. For a forward experiment, log actual first-seen and completion times.
4. **Separate simulated from observed latency.** Publication time is not the same as transcript availability, download completion or signal availability. Historical publication-plus-assumed-latency is a modeled assumption; forward first-seen latency is observable. Execute only after the trigger can be known and the signal is available.
5. **Prevent market-data leakage.** The evaluator must enforce candle-close availability for every timeframe. A higher-timeframe candle’s final high/low/close is unavailable at its opening timestamp. Apply the same discipline to revised fundamental or macro data if used.
6. **Test a frozen trading policy on future data.** Predefine how outlooks become trades, position limits, stops, holding periods and no-trade conditions. Record all variants and keep an untouched chronological test period. Include execution costs, spread, slippage and applicable funding/borrow assumptions. Compare with the same asset and period under a simple baseline, and calculate equity/drawdown including open positions.
7. **Test the incremental value of videos.** Compare a market-data-only policy, a simple text/sentiment baseline, the structured video extractor, and an independently labeled reference. This separates source quality, extraction error and strategy design. A complex agent debate is justified only if it improves held-out results enough to cover its cost and latency.

These are proposed research controls. No sample size, confidence threshold or profitability target is established merely by their presence. The decision to advance to trading requires evidence from the specific source, instruments and deployment conditions.

## Evidence status

- Creator identity: first-party channel and teaching site inspected; video channel fetch was sometimes throttled, but the indexed verified channel metadata and first-party cross-reference were available.
- Real example: publisher transcript read; original recording not listened to or watched. The linked original video ID was obtained from Cointelegraph’s embed, not guessed.
- Four small repositories: actual source files read through the GitHub connector, with repository heads recorded above. No execution or profitability reproduction performed.
- VideoConviction: full HTML paper read, selected source tree and license checked. The portfolio analysis is human-labeled and has important asset-universe sensitivity.
- Black working paper: primary-source abstract only.

Code findings are supported by the versioned primary-source file links above. Repository code was inspected directly; claims about execution or profitability were not reproduced.

## Dated correction — 13 November 2026

The original [YouTube watch page](https://www.youtube.com/watch?v=EdXslFg3u38) was subsequently retrieved. Its microformat identifies Cointelegraph as owner and gives both `publishDate` and `uploadDate` as `2026-09-02T08:01:27-07:00`, equivalent to **2026-09-02T15:01:27Z**. This resolves the video timestamp; it does not erase the different dates on the publisher’s episode and podcast pages. The genuine caption download contained **646 automatically generated English segments**. The baseline produced **46 unreviewed asset-mention claims and zero complete supported setups**. Acquisition occurred on 13 November, not in September; the captions have not been independently checked against audio. This is an import check, not an extraction-accuracy or profitability result. Metadata and limitations: [youtube-smoke.json](../validation/youtube-smoke.json).
