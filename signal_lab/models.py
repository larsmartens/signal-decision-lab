"""Small, explicit domain types shared by ingestion, decisions and replay."""
from __future__ import annotations

from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import datetime, timezone
import math
from typing import Any


def utc(value: str | datetime) -> datetime:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00")) if isinstance(value, str) else value
    if not isinstance(dt, datetime) or dt.tzinfo is None or dt.utcoffset() is None:
        raise ValueError("Timestamps must include a UTC offset, e.g. 2026-11-13T10:00:00Z")
    return dt.astimezone(timezone.utc)


def positive(value: float, name: str, *, zero: bool = False) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < 0 or (not zero and value == 0):
        raise ValueError(f"{name} must be {'non-negative' if zero else 'positive'}")


def jsonable(value: Any) -> Any:
    if is_dataclass(value) and not isinstance(value, type):
        return jsonable(asdict(value))
    if isinstance(value, datetime):
        return utc(value).isoformat().replace("+00:00", "Z")
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    return value


def strict_keys(cls: type, data: dict) -> None:
    if not isinstance(data, dict):
        raise ValueError(f"{cls.__name__} must be an object")
    extra = set(data) - {f.name for f in fields(cls)}
    if extra:
        raise ValueError(f"Unknown {cls.__name__} fields: {', '.join(sorted(extra))}")


@dataclass(frozen=True)
class Segment:
    id: str
    start: float
    end: float
    text: str

    def __post_init__(self) -> None:
        positive(self.start, "segment.start", zero=True)
        positive(self.end, "segment.end", zero=True)
        if self.end <= self.start or not self.id or not self.text.strip():
            raise ValueError("Segment needs an ID, text and an end after its start")


@dataclass(frozen=True)
class Transcript:
    source_id: str
    channel: str
    url: str
    published_at: datetime
    available_at: datetime
    segments: tuple[Segment, ...]
    kind: str = "manual"

    def __post_init__(self) -> None:
        object.__setattr__(self, "published_at", utc(self.published_at))
        object.__setattr__(self, "available_at", utc(self.available_at))
        if self.available_at < self.published_at:
            raise ValueError("Transcript cannot be available before publication")
        if self.kind not in {"manual", "youtube", "synthetic", "asr"}:
            raise ValueError("Unknown transcript kind")
        if not self.source_id or not self.channel or not self.segments:
            raise ValueError("Transcript needs source_id, channel and segments")
        if len({s.id for s in self.segments}) != len(self.segments):
            raise ValueError("Duplicate transcript segment IDs")
        if any(a.start > b.start for a, b in zip(self.segments, self.segments[1:])):
            raise ValueError("Transcript segments must be sorted")

    @classmethod
    def from_dict(cls, data: dict) -> Transcript:
        strict_keys(cls, data)
        obj = dict(data)
        for s in obj.get("segments", []):
            strict_keys(Segment, s)
        obj["segments"] = tuple(Segment(**s) for s in obj.get("segments", []))
        return cls(**obj)


@dataclass(frozen=True)
class Evidence:
    segment_id: str
    quote: str

    def __post_init__(self) -> None:
        if not self.segment_id or not self.quote.strip():
            raise ValueError("Evidence must cite a non-empty quote and segment")


@dataclass(frozen=True)
class Signal:
    id: str
    source_id: str
    asset: str
    side: str
    statement_type: str
    trigger: str
    level: float | None
    stop: float | None
    target: float | None
    timeframe_minutes: int | None
    horizon_minutes: int | None
    available_at: datetime
    expires_at: datetime | None
    evidence: tuple[Evidence, ...]
    issues: tuple[str, ...] = ()
    reviewed: bool = False
    extractor: str = "rules-v1"
    extracted_at: datetime | None = None
    reviewed_at: datetime | None = None

    def __post_init__(self) -> None:
        object.__setattr__(self, "available_at", utc(self.available_at))
        extracted = utc(self.extracted_at) if self.extracted_at is not None else self.available_at
        object.__setattr__(self, "extracted_at", extracted)
        if extracted > self.available_at:
            raise ValueError("Availability cannot precede extraction")
        if self.reviewed_at is not None:
            object.__setattr__(self, "reviewed_at", utc(self.reviewed_at))
            if self.reviewed_at < extracted or self.reviewed_at > self.available_at:
                raise ValueError("Review must follow extraction and precede decision availability")
        if self.expires_at is not None:
            object.__setattr__(self, "expires_at", utc(self.expires_at))
            # A late capture can already be expired; preserve it for audit and let
            # policy reject it instead of silently extending the source window.
        if not self.id or not self.source_id or not self.asset:
            raise ValueError("Signal needs id, source_id and asset")
        if self.side not in {"long", "short", "none"}:
            raise ValueError("Unknown signal side")
        if self.statement_type not in {"conditional", "actionable", "commentary", "negated", "retrospective"}:
            raise ValueError("Unknown statement type")
        if self.trigger not in {"close_above", "close_below", "none"}:
            raise ValueError("Unknown trigger")
        if not isinstance(self.reviewed, bool):
            raise ValueError("reviewed must be a boolean")
        for name in ("level", "stop", "target"):
            value = getattr(self, name)
            if value is not None:
                positive(value, name)
        for name in ("timeframe_minutes", "horizon_minutes"):
            value = getattr(self, name)
            if value is not None and (type(value) is not int or value <= 0):
                raise ValueError(f"{name} must be a positive integer")
        if not self.evidence:
            raise ValueError("Every extracted signal requires source evidence")

    @classmethod
    def from_dict(cls, data: dict) -> Signal:
        strict_keys(cls, data)
        obj = dict(data)
        for e in obj.get("evidence", []):
            strict_keys(Evidence, e)
        obj["evidence"] = tuple(Evidence(**e) for e in obj.get("evidence", []))
        obj["issues"] = tuple(obj.get("issues", ()))
        return cls(**obj)


@dataclass(frozen=True)
class Bar:
    asset: str
    open_time: datetime
    close_time: datetime
    open: float
    high: float
    low: float
    close: float
    volume: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "open_time", utc(self.open_time))
        object.__setattr__(self, "close_time", utc(self.close_time))
        if self.close_time <= self.open_time or not self.asset:
            raise ValueError("Bar needs an asset and close_time after open_time")
        for name in ("open", "high", "low", "close"):
            positive(getattr(self, name), name)
        positive(self.volume, "volume", zero=True)
        if self.low > min(self.open, self.close) or self.high < max(self.open, self.close) or self.low > self.high:
            raise ValueError("Inconsistent OHLC prices")

    @classmethod
    def from_dict(cls, data: dict) -> Bar:
        strict_keys(cls, data)
        return cls(**data)
