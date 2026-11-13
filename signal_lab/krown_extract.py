"""Auditable English directional-bias heuristics, separate from trade extraction.

The output describes research features, not source-authored orders. No model,
human review, probability calibration, price lookup, stop or target is implied.
Availability is deliberately left to a runner with source metadata.
"""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import Counter
from dataclasses import dataclass
import hashlib
import math
import re
from typing import Iterable

from .models import Transcript


VERSION = "krown-bias-rules-v1"
WORD = re.compile(r"[\w]+(?:['’][\w]+)*")
CUE = re.compile(
    r"\b(?:bullish|bearish|upside|downside|higher|lower|rally(?:ing)?|rallies|"
    r"bounce|bouncing|pullbacks?|pull back|sell[ -]?off|dump(?:ing)?|breakout|breakdown|go(?:ing)? long|go(?:ing)? short)\b", re.I,
)
NEGATIVE = {"bearish", "downside", "lower", "pullback", "pullbacks", "pull back", "selloff", "sell-off", "sell off", "dump", "dumping", "breakdown", "go short", "going short"}
ASSET = re.compile(
    r"\b(?P<btc>bitcoin|btc(?:usd[t]?)?)\b|"
    r"\b(?P<other>ethereum|ether|eth(?:usd[t]?)?|solana|sol|xrp|dogecoin|doge|"
    r"cardano|ada|chainlink|link|avalanche|avax|litecoin|ltc|polkadot|dot|bnb|sui|"
    r"gold|silver|dxy|nasdaq|spx|spy|altcoins?|stocks?|equities|traditional markets?)\b", re.I,
)
CONTRAST = re.compile(r"\b(?:but|however|whereas|instead|yet)\b", re.I)
BOUNDARY = re.compile(r"[.!?;](?:\s+|$)")
CONDITIONAL = re.compile(
    r"\b(?:if|when|whenever|unless|until|provided|providing|assuming|once|only after|as long as|"
    r"in the event|on condition|should we|that is where|that's where|while (?:above|below)|"
    r"contingent on|depending on|depends on|subject to|(?:this|that) (?:assumes|requires)|"
    r"after (?:it|bitcoin|btc|price) (?:reclaims?|breaks?|closes?|holds?|confirms?))\b", re.I,
)
HISTORY = re.compile(
    r"\b(?:yesterday|last (?:week|month|year)|earlier today|previously|historically|historical|"
    r"in the past|back in|backtest(?:ed|ing)?|used to|would have|had been|has been|have been|"
    r"i said|we said|i was|we were|was|were|expected|anticipated|thought|believed)\b", re.I,
)
NEGATION = re.compile(r"\b(?:not|no|never|neither|nor|cannot|can't|don't|doesn't|isn't|aren't|won't|wouldn't|without)\b", re.I)
REPORTED = re.compile(
    r"\b(?:according to|another trader|someone (?:said|says|thinks)|people (?:say|think)|"
    r"they (?:say|said|think)|he (?:says|said|thinks)|she (?:says|said|thinks)|"
    r"\w+ (?:says|said|writes|wrote|thinks|believes|claims|argues)|"
    r"(?:traders|analysts|people|investors|viewers|commenters|they) (?:are|remain|seem|look|think|believe)|"
    r"(?:viewer|trader|analyst|commenter|user|person) (?:sent|asked)|quoted?)\b", re.I,
)
HYPOTHETICAL = re.compile(r"\b(?:for example|hypothetic\w*|imagine|suppose|educational|illustration|if i were|would be (?:bullish|bearish))\b", re.I)
UNCERTAIN = re.compile(r"\b(?:don't know|do not know|no idea|unsure|uncertain|unclear|can't tell|cannot tell|either direction|both directions|coin flip|fifty.fifty|50.50)\b", re.I)
CORRECTION = re.compile(r"\b(?:sorry|correction|scratch that|take that back|let me correct|actually no)\b", re.I)
DERIVATIVES = re.compile(r"\b(?:perps?|perpetuals?|futures?|leverage|leveraged|options?)\b", re.I)
EXPLICIT_STANCE = re.compile(
    r"\b(?:i am|i'm|we are|we're|i remain|we remain|i feel|we feel|i lean|we lean|"
    r"my (?:current )?bias|our (?:current )?bias)\b", re.I,
)
EXPECTATION = re.compile(
    r"\b(?:i|we)\s+(?:(?:still|do|really|personally|currently|am|are)\s+){0,4}"
    r"(?:expect|expecting|anticipate|anticipating|think|believe|favor|favour|look(?:ing)?\s+for)\b", re.I,
)
PROBABILITY = re.compile(r"\b(?:bias|probabilit(?:y|ies)|odds|more likely|most likely|probably|favors?|favours?|base case|expectation)\b", re.I)
PRESENT = re.compile(r"\b(?:is|are|looks?|looking|remains?|still|currently|right now|today)\b", re.I)
BOUNDED_EXPECTATION = re.compile(r"\b(?:expect|expecting|anticipate|anticipating|looking for|look for|going to|gonna|will|should|likely)\b", re.I)
TENTATIVE_EXPECTATION = re.compile(r"\b(?:i'd|i would|we'd|we would)\s+(?:still\s+)?(?:be\s+)?looking for\b", re.I)


@dataclass(frozen=True)
class BiasConfig:
    name: str
    context_words: int
    asset_window_words: int
    minimum_support: int
    minimum_dominance: float
    allowed_rules: tuple[str, ...]
    lexical: bool = False


BIAS_CONFIGS = {
    "lexical": BiasConfig("lexical", 32, 70, 1, 0.0, ("word_mention",), True),
    "context_strict": BiasConfig("context_strict", 24, 40, 2, 0.5,
                                 ("explicit_stance", "explicit_expectation", "probability_bias")),
    "context_standard": BiasConfig("context_standard", 48, 70, 1, 0.25,
                                   ("explicit_stance", "explicit_expectation", "probability_bias", "present_market_description")),
    "context_broad": BiasConfig("context_broad", 80, 100, 1, 0.1,
                                ("explicit_stance", "explicit_expectation", "probability_bias", "present_market_description",
                                 "bounded_directional_expectation", "tentative_expectation")),
}
RULE_WEIGHT = {
    "word_mention": 1.0, "explicit_stance": 1.0, "explicit_expectation": 1.0,
    "probability_bias": 0.8, "present_market_description": 0.6,
    "bounded_directional_expectation": 0.5, "tentative_expectation": 0.4,
}


@dataclass(frozen=True)
class SourceSpan:
    segment_id: str
    start_seconds: float
    end_seconds: float
    char_start: int
    char_end: int
    quote: str


@dataclass(frozen=True)
class BiasEvent:
    id: str
    video_id: str
    variant: str
    asset: str | None
    direction: str
    candidate_direction: str
    strength: float
    accepted: bool
    rule: str
    unit_id: str
    start_seconds: float
    end_seconds: float
    evidence: tuple[SourceSpan, ...]
    cue_evidence: tuple[SourceSpan, ...]
    issues: tuple[str, ...]
    timeframe_minutes: int | None = None
    horizon_minutes: int | None = None
    derivatives_mentioned: bool = False


@dataclass(frozen=True)
class BiasSummary:
    video_id: str
    variant: str
    direction: str
    strength: float
    signed_score: float
    supporting_count: int
    conflicting_count: int
    excluded_count: int
    evidence: tuple[SourceSpan, ...]
    issues: tuple[str, ...]
    counts_by_reason: dict[str, int]
    positive_count: int
    negative_count: int
    extractor: str = VERSION
    score_kind: str = "weighted_directional_balance_heuristic"


def _config(config: BiasConfig | str) -> BiasConfig:
    if isinstance(config, str):
        if config not in BIAS_CONFIGS:
            raise ValueError(f"Unknown bias configuration: {config}")
        return BIAS_CONFIGS[config]
    if not isinstance(config, BiasConfig) or BIAS_CONFIGS.get(config.name) != config:
        raise ValueError("Use a registered, frozen bias configuration")
    return config


class _Source:
    def __init__(self, transcript: Transcript):
        self.transcript = transcript
        parts = []
        self.ranges = []
        offset = 0
        for segment in transcript.segments:
            parts.append(segment.text)
            self.ranges.append((offset, offset + len(segment.text), segment))
            offset += len(segment.text) + 1
        self.text = " ".join(parts)
        self.words = list(WORD.finditer(self.text))
        self.starts = [word.start() for word in self.words]
        self.assets = list(ASSET.finditer(self.text))
        self.boundaries = list(BOUNDARY.finditer(self.text))
        self.boundary_starts = [boundary.start() for boundary in self.boundaries]
        self.boundary_ends = [boundary.end() for boundary in self.boundaries]

    def sentence_bounds(self, start: int, end: int) -> tuple[int, int]:
        before = bisect_right(self.boundary_ends, start) - 1
        after = bisect_left(self.boundary_starts, end)
        left = self.boundary_ends[before] if before >= 0 else 0
        right = self.boundary_ends[after] if after < len(self.boundaries) else len(self.text)
        return left, right

    def unit_bounds(self, match: re.Match) -> tuple[int, int]:
        left, right = self.sentence_bounds(match.start(), match.end())
        before = list(CONTRAST.finditer(self.text, left, match.start()))
        after = CONTRAST.search(self.text, match.end(), right)
        return before[-1].end() if before else left, after.start() if after else right

    def qualifier_end(self, sentence_end: int) -> int:
        following = self.text[sentence_end:]
        if re.match(r"\s*(?:if|when|only if|but only|unless|provided|assuming|as long as|"
                    r"(?:this|that) (?:assumes|requires|depends)|actually no|scratch that|"
                    r"correction|sorry|let me correct|take that back)\b", following, re.I):
            _, end = self.sentence_bounds(sentence_end, sentence_end)
            return end
        return sentence_end

    def spans(self, start: int, end: int) -> tuple[SourceSpan, ...]:
        result = []
        for begin, finish, segment in self.ranges:
            left, right = max(start, begin), min(end, finish)
            if left < right and self.text[left:right].strip():
                result.append(SourceSpan(segment.id, segment.start, segment.end,
                                         left - begin, right - begin, self.text[left:right]))
        return tuple(result)

    def bounds(self, match: re.Match, radius: int) -> tuple[int, int]:
        index = max(0, bisect_right(self.starts, match.start()) - 1)
        left = self.words[max(0, index - radius)].start()
        right_index = min(len(self.words) - 1, index + radius)
        right = self.words[right_index + 1].start() if right_index + 1 < len(self.words) else len(self.text)
        previous = list(BOUNDARY.finditer(self.text, left, match.start()))
        if previous:
            left = previous[-1].end()
        following = BOUNDARY.search(self.text, match.end(), right)
        if following:
            right = following.end()
        contrasts_before = list(CONTRAST.finditer(self.text, left, match.start()))
        if contrasts_before:
            left = contrasts_before[-1].end()
        contrast_after = CONTRAST.search(self.text, match.end(), right)
        if contrast_after:
            right = contrast_after.start()
        return left, right

    def asset(self, start: int, end: int, cue: re.Match, window: int) -> tuple[re.Match | None, str | None]:
        local = [match for match in self.assets if start <= match.start() < end]
        if local:
            kinds = {bool(match.group("btc")) for match in local}
            if len(kinds) > 1:
                return None, "ambiguous_asset_context"
            if True not in kinds:
                return None, "other_asset_context"
            return min(local, key=lambda match: abs(match.start() - cue.start())), None
        previous = [match for match in self.assets if match.end() <= cue.start()]
        if not previous:
            return None, "unbound_asset"
        nearest = previous[-1]
        distance = bisect_left(self.starts, cue.start()) - bisect_left(self.starts, nearest.start())
        if distance > window:
            return None, "unbound_asset"
        if not nearest.group("btc"):
            return None, "other_asset_context"
        return nearest, None


def _normalize(text: str) -> str:
    return text.lower().replace("’", "'")


def _semantic_rule(context: str, prefix: str, cue: str) -> str | None:
    if EXPECTATION.search(prefix):
        return "explicit_expectation"
    if EXPLICIT_STANCE.search(prefix) and cue in {"bullish", "bearish", "go long", "go short", "going long", "going short"}:
        return "explicit_stance"
    if PROBABILITY.search(context):
        return "probability_bias"
    if TENTATIVE_EXPECTATION.search(prefix):
        return "tentative_expectation"
    if cue in {"bullish", "bearish"} and PRESENT.search(context):
        return "present_market_description"
    if BOUNDED_EXPECTATION.search(prefix):
        return "bounded_directional_expectation"
    return None


def _exclusions(context: str, sentence: str, prefix: str, suffix: str, cue: str) -> list[str]:
    issues = []
    if CONDITIONAL.search(sentence):
        issues.append("conditional_context")
    current_reset = re.search(r"\b(?:now|today|currently|right now)\b", context)
    if HISTORY.search(context) or (HISTORY.search(sentence) and not current_reset):
        issues.append("historical_context")
    if NEGATION.search(context):
        issues.append("negated_context")
    if HYPOTHETICAL.search(sentence) or (re.search(r"\bwould\b", context) and not TENTATIVE_EXPECTATION.search(prefix)):
        issues.append("hypothetical_or_educational_context")
    if re.search(r"\b(?:i|we)(?: will|'ll)\s+be\s+(?:bullish|bearish)\b", context):
        issues.append("future_stance_not_current")
    if REPORTED.search(sentence):
        issues.append("reported_speech")
    if "?" in context or UNCERTAIN.search(context):
        issues.append("question_or_uncertainty")
    if CORRECTION.search(sentence):
        issues.append("unresolved_correction")
    if re.search(r"\b(?:could|may|might)\b", prefix):
        issues.append("possibility_without_directional_preference")
    if cue in {"bullish", "bearish"} and re.match(r"\s+(?:(?:hidden|regular|potential|moving[ -]average)\s+){0,3}(?:divergence|engulfing|crossover|cross|pattern|signal|indicator|reset)\b", suffix):
        issues.append("indicator_description_only")
    if cue in {"bullish", "bearish"} and re.search(r"\b(?:rsi|stoch\w*|macd|oscillator|indicator|moving[ -]averages?)\b", context):
        issues.append("indicator_description_only")
    if cue in {"higher", "lower"} and re.match(r"\s+(?:time[ -]?frames?|highs?|lows?|probabilit\w*|odds|volatility|risk|volume|interest|funding)\b", suffix):
        issues.append("non_directional_comparison")
    if re.search(r"\b(?:versus|vs\.?|against)\s+(?:bitcoin|btc)\b", sentence):
        issues.append("relative_asset_view")
    if re.search(r"\b(?:bitcoin|btc)(?:'s)?\s+(?:dominance|hashrate|hash rate|funding|open interest)\b", sentence):
        issues.append("different_bitcoin_metric")
    subject = re.match(r"\s+(?:on|for|about)\s+([\w]+)", suffix)
    if subject and subject[1] not in {"bitcoin", "btc", "btcusd", "btcusdt", "this", "that", "it", "the", "a", "an", "next", "q1", "q2", "q3", "q4", "now", "today", "tomorrow"}:
        issues.append("different_stated_subject")
    return issues


AMOUNTS = {"one": 1, "two": 2, "three": 3, "four": 4, "six": 6, "eight": 8, "twelve": 12, "twenty four": 24}
AMOUNT = r"(?:\d+|twenty[ -]four|one|two|three|four|six|eight|twelve)"
UNIT = r"(?:minutes?|hours?|days?|weeks?)"


def _durations(context: str) -> tuple[int | None, int | None, list[str]]:
    def value(amount: str, unit: str) -> int:
        normalized = amount.replace("-", " ")
        count = int(normalized) if normalized.isdigit() else AMOUNTS[normalized]
        return count * {"m": 1, "h": 60, "d": 1440, "w": 10080}[unit[0]]

    frames = {value(match[1], match[2]) for match in re.finditer(rf"(?<![\w.])({AMOUNT})[ -]+({UNIT})\s+(?:chart|time[ -]?frame|candle)\b", context)}
    for word, minutes in (("hourly", 60), ("daily", 1440), ("weekly", 10080)):
        if re.search(rf"\b{word}\s+(?:chart|time[ -]?frame|candle)\b", context):
            frames.add(minutes)
    horizons = {value(match[1], match[2]) for match in re.finditer(rf"\b(?:over|within|in|for)?\s*(?:the\s+)?next\s+({AMOUNT})[ -]+({UNIT})\b", context)}
    issues = []
    if len(frames) > 1:
        issues.append("multiple_stated_chart_timeframes")
    if len(horizons) > 1:
        issues.append("multiple_stated_horizons")
    return next(iter(frames)) if len(frames) == 1 else None, next(iter(horizons)) if len(horizons) == 1 else None, issues


def extract_bias_events(transcript: Transcript, config: BiasConfig | str = "context_standard") -> list[BiasEvent]:
    """Return source-grounded candidate cues, including explicit abstentions.

    Contextual candidates receive ``direction='flat'`` when excluded. The
    lexical comparator deliberately omits scope/negation/history filtering.
    Every variant still requires a bounded Bitcoin asset reference.
    """
    selected = _config(config)
    source = _Source(transcript)
    events = []
    for match in CUE.finditer(source.text):
        start, end = source.bounds(match, selected.context_words)
        context = _normalize(source.text[start:end])
        prefix = _normalize(source.text[start:match.start()])
        cue = _normalize(match[0])
        asset, asset_issue = source.asset(start, end, match, selected.asset_window_words)
        full_start, full_end = source.sentence_bounds(match.start(), match.end())
        full_end = source.qualifier_end(full_end)
        if asset is not None:
            anchor_start, _ = source.sentence_bounds(asset.start(), asset.end())
            full_start = min(full_start, anchor_start)
        sentence = _normalize(source.text[full_start:full_end])
        unit_start, unit_end = source.unit_bounds(match)
        full_context = _normalize(source.text[unit_start:unit_end])
        full_prefix = _normalize(source.text[unit_start:match.start()])
        full_suffix = _normalize(source.text[match.end():unit_end])
        issues = [asset_issue] if asset_issue else []
        rule = "word_mention" if selected.lexical else _semantic_rule(context, prefix, cue)
        if not selected.lexical:
            issues += _exclusions(full_context, sentence, full_prefix, full_suffix, cue)
            if rule is None:
                issues.append("no_current_directional_claim")
            elif rule not in selected.allowed_rules:
                issues.append("rule_outside_variant_scope")
        frame, horizon, duration_issues = _durations(context)
        accepted = not issues
        direction = "short" if cue in NEGATIVE else "long"
        evidence_start = min(start, full_start)
        evidence_end = max(end, full_end)
        evidence = source.spans(evidence_start, evidence_end)
        cue_evidence = source.spans(match.start(), match.end())
        identity = f"{VERSION}|{selected.name}|{transcript.source_id}|{match.start()}|{match.end()}"
        normalized_unit = re.sub(r"\s+", " ", full_context).strip(" ,.;:!?")
        unit_id = hashlib.sha256(f"{transcript.source_id}|{normalized_unit}".encode()).hexdigest()[:16]
        events.append(BiasEvent(
            id=hashlib.sha256(identity.encode()).hexdigest()[:16], video_id=transcript.source_id,
            variant=selected.name, asset="BTCUSDT" if asset else None,
            direction=direction if accepted else "flat", candidate_direction=direction,
            strength=RULE_WEIGHT[rule] if accepted and rule else 0.0, accepted=accepted,
            rule=f"{VERSION}:{selected.name}:{rule or 'no_supported_rule'}", unit_id=unit_id,
            start_seconds=min(span.start_seconds for span in cue_evidence),
            end_seconds=max(span.end_seconds for span in cue_evidence), evidence=evidence,
            cue_evidence=cue_evidence, issues=tuple(dict.fromkeys(issues + duration_issues)),
            timeframe_minutes=frame, horizon_minutes=horizon,
            derivatives_mentioned=bool(DERIVATIVES.search(context)),
        ))
    return events


def _publication_evidence(event: BiasEvent, max_words: int = 25) -> tuple[SourceSpan, ...]:
    """One compact exact quote; the caller must share its budget across variants."""
    cue = event.cue_evidence[0]
    source = next(span for span in event.evidence if span.segment_id == cue.segment_id)
    words = list(WORD.finditer(source.quote))
    cue_at = max(0, cue.char_start - source.char_start)
    index = max(0, bisect_right([word.start() for word in words], cue_at) - 1)
    left_index = max(0, index - max_words // 2)
    right_index = min(len(words), left_index + max_words)
    if right_index - left_index < max_words:
        left_index = max(0, right_index - max_words)
    left, right = words[left_index].start(), words[right_index - 1].end()
    return (SourceSpan(source.segment_id, source.start_seconds, source.end_seconds,
                       source.char_start + left, source.char_start + right, source.quote[left:right]),)


def aggregate_bias(events: Iterable[BiasEvent], config: BiasConfig | str = "context_standard", *, video_id: str | None = None) -> BiasSummary:
    selected = _config(config)
    candidates = list(events)
    sources = {event.video_id for event in candidates}
    if len(sources) > 1 or (video_id and sources and sources != {video_id}):
        raise ValueError("A bias summary must contain exactly one video's events")
    if any(event.variant != selected.name for event in candidates):
        raise ValueError("A bias summary cannot mix extraction variants")
    source_id = video_id or next(iter(sources), "")
    groups: dict[tuple[str, str], BiasEvent] = {}
    for event in candidates:
        if event.accepted:
            key = event.unit_id, event.direction
            if key not in groups or groups[key].strength < event.strength:
                groups[key] = event
    positive = [event for event in groups.values() if event.direction == "long"]
    negative = [event for event in groups.values() if event.direction == "short"]
    plus, minus = sum(event.strength for event in positive), sum(event.strength for event in negative)
    score = (plus - minus) / (plus + minus) if plus + minus else 0.0
    winner = positive if score > 0 else negative if score < 0 else []
    loser = negative if score > 0 else positive if score < 0 else []
    eligible = len(winner) >= selected.minimum_support and abs(score) >= selected.minimum_dominance and score != 0
    direction = ("long" if score > 0 else "short") if eligible else "flat"
    issues = ["heuristic_score_not_probability", "research_view_not_source_authored_order"]
    if selected.lexical:
        issues.append("lexical_baseline_ignores_semantic_scope")
    if positive and negative:
        issues.append("conflicting_current_views")
    if not groups:
        issues.append("no_supported_current_view")
    elif len(winner) < selected.minimum_support:
        issues.append("insufficient_independent_support")
    elif not eligible:
        issues.append("insufficient_directional_dominance")
    reasons: Counter[str] = Counter()
    for event in candidates:
        reasons.update(event.issues if not event.accepted else (event.rule.rsplit(":", 1)[-1],))
    representative = (winner or list(groups.values()) or candidates)
    evidence = _publication_evidence(representative[0]) if representative else ()
    return BiasSummary(
        video_id=source_id, variant=selected.name, direction=direction,
        strength=abs(score) if eligible else 0.0, signed_score=score,
        supporting_count=len(winner) if eligible else 0, conflicting_count=len(loser) if eligible else min(len(positive), len(negative)),
        excluded_count=sum(not event.accepted for event in candidates), evidence=evidence,
        issues=tuple(issues), counts_by_reason=dict(sorted(reasons.items())),
        positive_count=len(positive), negative_count=len(negative),
    )


def extract_bias(transcript: Transcript, config: BiasConfig | str = "context_standard") -> BiasSummary:
    return aggregate_bias(extract_bias_events(transcript, config), config, video_id=transcript.source_id)


def validate_bias_grounding(event: BiasEvent, transcript: Transcript) -> None:
    """Check exact provenance, cue polarity and weight consistency, not truth.

    This does not substitute for human semantic review or certify that a finite
    set of English scope rules understands every source statement.
    """
    if event.video_id != transcript.source_id:
        raise ValueError("Bias event source does not match transcript")
    if not event.evidence or not event.cue_evidence:
        raise ValueError("Bias event needs source evidence and a cue span")
    selected = _config(event.variant)
    cue = _normalize(" ".join(span.quote for span in event.cue_evidence))
    if CUE.fullmatch(cue) is None:
        raise ValueError("Bias cue does not match the supported directional vocabulary")
    candidate = "short" if cue in NEGATIVE else "long"
    if event.candidate_direction != candidate or event.direction != (candidate if event.accepted else "flat"):
        raise ValueError("Bias direction does not match its source cue and acceptance state")
    rule = event.rule.rsplit(":", 1)[-1]
    if not event.rule.startswith(f"{VERSION}:{selected.name}:"):
        raise ValueError("Bias rule provenance does not match its extraction variant")
    expected_strength = RULE_WEIGHT.get(rule, 0.0) if event.accepted else 0.0
    if not math.isfinite(event.strength) or not 0 <= event.strength <= 1 or event.strength != expected_strength:
        raise ValueError("Bias strength does not match its documented heuristic rule weight")
    if event.accepted and (rule not in selected.allowed_rules or event.asset != "BTCUSDT"):
        raise ValueError("Accepted bias has an unsupported rule or asset")
    if (event.start_seconds, event.end_seconds) != (
        min(span.start_seconds for span in event.cue_evidence),
        max(span.end_seconds for span in event.cue_evidence),
    ):
        raise ValueError("Bias event timestamp does not match its cue segments")
    segments = {segment.id: segment for segment in transcript.segments}
    for span in event.evidence + event.cue_evidence:
        segment = segments.get(span.segment_id)
        if segment is None or not (0 <= span.char_start < span.char_end <= len(segment.text)):
            raise ValueError("Bias evidence offset is outside its source segment")
        if segment.text[span.char_start:span.char_end] != span.quote:
            raise ValueError("Bias evidence is not an exact source substring")
        if (span.start_seconds, span.end_seconds) != (segment.start, segment.end):
            raise ValueError("Bias evidence timestamp does not match its source segment")
    if event.accepted and not re.search(r"\b(?:bitcoin|btc(?:usdt|usd)?)\b", " ".join(span.quote for span in event.evidence), re.I):
        raise ValueError("Accepted bias lacks a cited Bitcoin reference")
