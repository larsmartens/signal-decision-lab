"""Conservative English baseline. It never completes an author's trading strategy."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import hashlib
import re

from .models import Evidence, Signal, Transcript, utc

NUMBER = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?[kK]?"
NUMBER_END = r"(?![\w,]|\.\d)"
ASSETS = {"BTCUSDT": r"\b(?:bitcoin|btc(?:usdt|usd)?)\b", "ETHUSDT": r"\b(?:ethereum|ether|eth(?:usdt|usd)?)\b"}


def number(value: str) -> float:
    return float(value.lower().rstrip("k").replace(",", "")) * (1000 if value.lower().endswith("k") else 1)


def _price(text: str, label: str) -> float | None:
    pattern = rf"\b{label}\s*(?:(?:at|is|of)\s+)?\$?({NUMBER}){NUMBER_END}"
    found = list(re.finditer(pattern, text, re.I))
    for match in found:
        if re.match(r"\s*(?:%|percent\b|bps\b|basis points\b|to\b|or\b|through\b|[-–]|\.\.)", text[match.end():], re.I):
            return None
    values = {number(m[1]) for m in found}
    return next(iter(values)) if len(values) == 1 else None


def _minutes(amount: str, unit: str) -> int:
    return int(amount) * ({"m": 1, "h": 60, "d": 1440}[unit.lower()[0]])


def _duration(text: str, *, horizon: bool = False) -> int | None:
    if horizon:
        matches = re.findall(r"\b(?:valid|expires?)\s+(?:for|in)\s+(\d+)\s*(minutes?|hours?|days?|[mhd])\b", text, re.I)
    else:
        matches = re.findall(r"(?<![\w.])(\d+)[ -]?(minutes?|hours?|days?|[mhd])\s+(?:candle\s+)?closes?\b", text, re.I)
    values = {_minutes(amount, unit) for amount, unit in matches}
    return next(iter(values)) if len(values) == 1 else None


def _classify(text: str) -> tuple[str, str]:
    lowered = text.lower().replace("’", "'")
    if re.search(r"\b(?:yesterday|last week|last month|earlier today|had bought|had sold|would have|went long|went short|bought|sold|entered a trade|took a trade)\b", lowered):
        return "retrospective", "none"
    if re.search(r"\b(?:do not|don't|never|not|no|no longer|wouldn't|won't|can't|cannot)\s+(?:(?:a|go|take|enter|recommend|would|will)\s+){0,3}(?:buy|sell|long|short|trade|entry|signal)\b", lowered):
        return "negated", "none"
    if re.search(r"\b(?:for example|hypothetical(?:ly)?|imagine|suppose|educational|illustration|if i were|another trader said|someone said)\b", lowered):
        return "commentary", "none"
    long = bool(re.search(r"\b(?:long|buy)\b", lowered))
    short = bool(re.search(r"\b(?:short|sell)\b", lowered))
    side = "long" if long and not short else "short" if short and not long else "none"
    if side == "none":
        return "commentary", side
    return ("conditional" if re.search(r"\b(?:if|when|only after|provided)\b", lowered) else "actionable"), side


def unsupported_condition(text: str) -> bool:
    return bool(re.search(r"\b(?:rsi|ema|sma|volume|volatility|unless|except|not until|breaks? and holds?|retest|funding|weekly trend|daily trend|monthly trend|trend is|and the|as long as|assuming|provided|percent)\b|\d\s*%", text, re.I))


def supported_language(text: str) -> bool:
    """The executable grammar is deliberately bounded; all other text stays a claim.

    This complements the reviewer gate. A list of suspicious words cannot prove
    that a free-form sentence has no extra condition, attribution or correction.
    """
    asset = r"(?:bitcoin|btc(?:usdt|usd)?|ethereum|ether|eth(?:usdt|usd)?)"
    action = r"(?:buy|sell|(?:go\s+)?long|(?:go\s+)?short)"
    candle = r"(?:the\s+)?\d+[ -]?(?:minutes?|hours?|days?|[mhd])\s+(?:candle\s+)?closes?"
    condition = rf"{candle}\s+(?:strictly\s+)?(?:above|below)\s+\$?{NUMBER}(?:\s+(?:is confirmed|occurs))?"
    first = rf"(?:i\s+(?:would|will)\s+)?{action}\s+{asset}\s+(?:if|when)\s+{condition}"
    second = rf"(?:for\s+)?{asset}\s*[,;:]?\s*(?:if|when)\s+{condition}\s*[,;:]?\s*(?:then\s+)?{action}"
    third = rf"(?:if|when)\s+{condition}\s*[,;:]?\s*(?:then\s+)?{action}\s+{asset}"
    fourth = rf"{asset}\s*:\s*{action}\s+(?:if|when)\s+{condition}"
    separator = r"\s*[.;,]\s*"
    stop = rf"stop(?:[ -]loss)?\s*(?:(?:at|is|of)\s+)?\$?{NUMBER}"
    target = rf"target\s*(?:(?:at|is|of)\s+)?\$?{NUMBER}"
    horizon = r"(?:valid\s+for|expires?\s+in)\s+\d+\s*(?:minutes?|hours?|days?|[mhd])"
    pattern = rf"(?:{first}|{second}|{third}|{fourth}){separator}{stop}{separator}{target}{separator}{horizon}\s*[.!]?"
    return re.fullmatch(pattern, text.strip(), re.I) is not None


def missing_fields(signal: Signal) -> list[str]:
    issues = []
    for key in ("level", "stop", "target", "timeframe_minutes", "horizon_minutes"):
        if getattr(signal, key) is None:
            issues.append(f"missing_{key}")
    if signal.trigger == "none":
        issues.append("missing_trigger")
    return issues


def extract_rules(transcript: Transcript, *, extracted_at: datetime | None = None) -> list[Signal]:
    available = max(transcript.available_at, utc(extracted_at) if extracted_at else transcript.available_at)
    results = []
    for segment in transcript.segments:
        text = segment.text
        assets = [asset for asset, pattern in ASSETS.items() if re.search(pattern, text, re.I)]
        if not assets:
            continue
        statement_type, side = _classify(text)
        found = re.findall(rf"\bcloses?\s+(?:strictly\s+)?(above|below)\s+\$?({NUMBER}){NUMBER_END}", text, re.I)
        trigger, level = (f"close_{found[0][0].lower()}", number(found[0][1])) if len(found) == 1 else ("none", None)
        horizon = _duration(text, horizon=True)
        issues = []
        if len(assets) > 1 or len(found) > 1 or (re.search(r"\blong\b", text, re.I) and re.search(r"\bshort\b", text, re.I)):
            issues.append("ambiguous_multiple_setups")
        if unsupported_condition(text):
            issues.append("unsupported_condition")
        if statement_type in {"conditional", "actionable"} and not supported_language(text):
            issues.append("unsupported_language")
        for asset in assets:
            identity = f"{transcript.source_id}|{segment.id}|{asset}|{text}"
            signal = Signal(
                id=hashlib.sha256(identity.encode()).hexdigest()[:16], source_id=transcript.source_id,
                asset=asset, side=side, statement_type=statement_type, trigger=trigger, level=level,
                stop=_price(text, r"stop(?:[ -]loss)?"), target=_price(text, "target"),
                timeframe_minutes=_duration(text), horizon_minutes=horizon,
                available_at=available, expires_at=transcript.published_at + timedelta(minutes=horizon) if horizon else None,
                evidence=(Evidence(segment.id, text),), issues=tuple(issues), reviewed=False,
            )
            signal = replace(signal, issues=tuple(sorted(set(issues + missing_fields(signal)))))
            results.append(signal)
    return results


def validate_grounding(signal: Signal, transcript: Transcript) -> None:
    if signal.source_id != transcript.source_id:
        raise ValueError("Signal source_id does not match its transcript")
    if signal.available_at < transcript.available_at:
        raise ValueError("Signal cannot precede transcript availability")
    if signal.extracted_at is None or signal.extracted_at < transcript.available_at:
        raise ValueError("Extraction cannot precede transcript availability")
    segments = {s.id: s for s in transcript.segments}
    for evidence in signal.evidence:
        segment = segments.get(evidence.segment_id)
        if segment is None or evidence.quote not in segment.text:
            raise ValueError("Evidence quote is not an exact substring of its source segment")
    text = " ".join(e.quote for e in signal.evidence)
    context = " ".join(segments[e.segment_id].text for e in signal.evidence)
    if signal.asset not in ASSETS or not re.search(ASSETS[signal.asset], text, re.I):
        raise ValueError("Asset is not grounded in the cited text")
    # Numeric presence alone is insufficient: bind each number to its stated role.
    roles = {"stop": _price(text, r"stop(?:[ -]loss)?"), "target": _price(text, "target")}
    triggers = re.findall(rf"\bcloses?\s+(?:strictly\s+)?(above|below)\s+\$?({NUMBER}){NUMBER_END}", text, re.I)
    for role, grounded in roles.items():
        if getattr(signal, role) is not None and getattr(signal, role) != grounded:
            raise ValueError(f"Ungrounded or ambiguous {role}")
    if signal.level is not None and not any(signal.trigger == f"close_{direction.lower()}" and signal.level == number(value) for direction, value in triggers):
        raise ValueError("Entry level or comparator is not grounded")
    for field, grounded in (("timeframe_minutes", _duration(text)), ("horizon_minutes", _duration(text, horizon=True))):
        if getattr(signal, field) is not None and getattr(signal, field) != grounded:
            raise ValueError(f"Ungrounded {field}")
    classified, side = _classify(context)
    if classified in {"negated", "retrospective"} and signal.statement_type not in {classified, "commentary"}:
        raise ValueError("Negation or historical context was dropped")
    if signal.side != "none" and signal.side != side:
        raise ValueError("Trade direction is not grounded")
    if signal.statement_type in {"conditional", "actionable"} and not supported_language(context) and "unsupported_language" not in signal.issues:
        raise ValueError("Source contains language outside the executable grammar")
    horizon = signal.horizon_minutes
    if horizon is not None and signal.expires_at != transcript.published_at + timedelta(minutes=horizon):
        raise ValueError("Expiry must preserve the source publication window")
    if unsupported_condition(context) and "unsupported_condition" not in signal.issues:
        raise ValueError("An unsupported condition was omitted from the evidence")


def review_signal(signal: Signal, transcript: Transcript, *, reviewed_at: datetime) -> Signal:
    validate_grounding(signal, transcript)
    at = utc(reviewed_at)
    if at < signal.available_at:
        raise ValueError("Review cannot happen before the signal exists")
    if signal.issues or missing_fields(signal):
        raise ValueError("Resolve missing/unsupported fields before approving a signal")
    if signal.statement_type not in {"conditional", "actionable"} or signal.side == "none":
        raise ValueError("Commentary, negated and retrospective claims cannot be approved as entries")
    if signal.expires_at is None or at >= signal.expires_at:
        raise ValueError("Signal expired before review")
    # Keep original expiry: delayed review must never extend the author's setup window.
    return replace(signal, reviewed=True, reviewed_at=at, available_at=at)
