"""Timestamp-preserving imports; network/ASR providers are explicit optional paths."""
from __future__ import annotations

from datetime import datetime, timezone
import csv
import html
import json
from pathlib import Path
import re
from urllib.parse import parse_qs, urlparse

from .models import Bar, Segment, Transcript, jsonable, utc


def read_json(path: str | Path):
    def invalid_constant(value):
        raise ValueError(f"Non-finite JSON number: {value}")
    return json.loads(Path(path).read_text(encoding="utf-8-sig"), parse_constant=invalid_constant)


def write_json(path: str | Path, data) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(jsonable(data), indent=2, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")
    temporary.replace(target)


def _seconds(value: str) -> float:
    parts = value.replace(",", ".").split(":")
    if len(parts) not in {2, 3}:
        raise ValueError("Invalid caption timestamp")
    numbers = [float(p) for p in parts]
    if any(n < 0 for n in numbers) or any(n >= 60 for n in numbers[-2:]):
        raise ValueError("Invalid caption timestamp range")
    return sum(n * 60 ** i for i, n in enumerate(reversed(numbers)))


def parse_captions(text: str) -> tuple[Segment, ...]:
    segments: list[Segment] = []
    pattern = re.compile(r"^(\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3})\s+-->\s+(\d{1,2}:\d{2}(?::\d{2})?[.,]\d{3})(?:\s.*)?$")
    lines = text.replace("\r\n", "\n").splitlines()
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if re.match(r"^(?:NOTE(?:\s|$)|STYLE$|REGION$)", line):
            index += 1
            while index < len(lines) and lines[index].strip():
                index += 1
            continue
        match = pattern.match(line)
        index += 1
        if not match:
            if "-->" in line:
                raise ValueError("Malformed caption timing; refusing a partial transcript")
            continue
        content = []
        while index < len(lines) and lines[index].strip():
            if "-->" in lines[index] and not pattern.match(lines[index].strip()):
                raise ValueError("Malformed caption timing; refusing a partial transcript")
            if pattern.match(lines[index].strip()):
                break
            content.append(lines[index].strip())
            index += 1
        clean = html.unescape(re.sub(r"<[^>]*>", "", " ".join(content))).strip()
        if clean:
            segments.append(Segment(f"s{len(segments)+1}", _seconds(match[1]), _seconds(match[2]), clean))
    if not segments:
        raise ValueError("No timestamped captions found; use WebVTT, SRT or canonical JSON")
    return tuple(segments)


def load_transcript(path: str | Path, metadata: str | Path | None = None) -> Transcript:
    path = Path(path)
    if path.suffix.lower() == ".json":
        return Transcript.from_dict(read_json(path))
    if path.suffix.lower() not in {".vtt", ".srt"} or metadata is None:
        raise ValueError("VTT/SRT requires --metadata with source_id, channel, url, published_at and available_at")
    data = read_json(metadata)
    if "segments" in data:
        raise ValueError("Caption metadata must not contain segments")
    data["segments"] = jsonable(parse_captions(path.read_text(encoding="utf-8-sig")))
    return Transcript.from_dict(data)


def load_bars(path: str | Path) -> list[Bar]:
    path = Path(path)
    if path.suffix.lower() == ".csv":
        with path.open(newline="", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        for row in rows:
            for field in ("open", "high", "low", "close", "volume"):
                if field in row:
                    row[field] = float(row[field])
    else:
        rows = read_json(path)
    if not isinstance(rows, list) or not rows:
        raise ValueError("Market data must be a non-empty array or CSV of OHLC bars")
    return [Bar.from_dict(row) for row in rows]


def youtube_video_id(url: str) -> str:
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password:
        raise ValueError("Use an HTTPS YouTube watch URL")
    if parsed.hostname in {"www.youtube.com", "youtube.com"} and parsed.path == "/watch":
        value = parse_qs(parsed.query).get("v", [""])[0]
    elif parsed.hostname == "youtu.be":
        value = parsed.path.strip("/")
    else:
        raise ValueError("Use youtube.com/watch?v=... or youtu.be/... (no other hosts)")
    if not re.fullmatch(r"[A-Za-z0-9_-]{11}", value):
        raise ValueError("Invalid YouTube video ID")
    return value


def fetch_youtube(url: str, *, channel: str, published_at: str, languages: tuple[str, ...] = ("en",)) -> Transcript:
    video_id = youtube_video_id(url)
    published = utc(published_at)
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError as exc:
        raise ValueError("Install the optional youtube extra: python -m pip install '.[youtube]'") from exc
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=list(languages))
    except Exception as exc:
        raise ValueError(f"Caption fetch unavailable ({type(exc).__name__}); export VTT/SRT and use extract --metadata instead") from exc
    segments = tuple(Segment(f"s{i+1}", row.start, row.start + row.duration, row.text) for i, row in enumerate(fetched) if row.duration > 0 and row.text.strip())
    return Transcript(video_id, channel, f"https://www.youtube.com/watch?v={video_id}", published, datetime.now(timezone.utc), segments, "youtube")


def transcribe_media(path: str | Path, metadata: dict, *, model: str = "small.en") -> Transcript:
    media = Path(path)
    if not media.is_file():
        raise ValueError("Local audio/video file not found")
    if model not in {"tiny.en", "base.en", "small.en", "medium.en", "large-v3"}:
        raise ValueError("Unsupported ASR model name")
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:
        raise ValueError("Install the optional asr extra: python -m pip install '.[asr]'") from exc
    engine = WhisperModel(model, device="cpu", compute_type="int8")
    generated, _ = engine.transcribe(str(media), beam_size=5, vad_filter=True)
    segments = tuple(Segment(f"s{i+1}", s.start, s.end, s.text.strip()) for i, s in enumerate(generated) if s.end > s.start and s.text.strip())
    data = dict(metadata)
    data.update(kind="asr", available_at=jsonable(datetime.now(timezone.utc)), segments=jsonable(segments))
    return Transcript.from_dict(data)
