"""Publish semantic claim references while keeping complete captions private.

Evidence offsets use Python string indices (Unicode code points), not byte
offsets. Loading requires the exact canonical transcript, including metadata.
The manifest carries authored paraphrases; it never copies evidence quotes.
"""
from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from .ingest import load_transcript
from .models import Transcript, jsonable
from .semantic_claims import FIELD_NAMES, LIST_FIELD_NAMES, SemanticClaim, prepare_state


FORMAT = "semantic_claim_references"


def _exact(value: Any, names: set[str], label: str) -> None:
    if not isinstance(value, dict) or set(value) != names:
        raise ValueError(f"Invalid {label} fields")


def _object(pairs: list[tuple[str, Any]]) -> dict:
    result: dict = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("Duplicate JSON field")
        result[name] = value
    return result


def _invalid_number(value: str) -> None:
    raise ValueError("Non-finite JSON number")


def _read(path: str | Path) -> dict:
    value = json.loads(Path(path).read_text(encoding="utf-8"), object_pairs_hook=_object,
                       parse_constant=_invalid_number)
    if not isinstance(value, dict):
        raise ValueError("Claim input must be an object")
    return value


def transcript_sha256(transcript: Transcript) -> str:
    canonical = json.dumps(jsonable(transcript), sort_keys=True, separators=(",", ":"),
                           ensure_ascii=False, allow_nan=False).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def _source(transcript: Transcript) -> dict:
    return {"canonical_transcript_sha256": transcript_sha256(transcript),
            "url": transcript.url, "channel": transcript.channel, "kind": transcript.kind,
            "published_at": jsonable(transcript.published_at),
            "captions_available_at": jsonable(transcript.available_at)}


def _private_bundle(value: Any) -> tuple[str, list[SemanticClaim]]:
    _exact(value, {"schema_version", "selection_basis", "claims"}, "private claim bundle")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("Unsupported claim schema version")
    selection = value["selection_basis"]
    if not isinstance(selection, str) or not selection.strip() or len(selection) > 4000:
        raise ValueError("Selection basis must be non-empty bounded text")
    if not isinstance(value["claims"], list) or not value["claims"]:
        raise ValueError("A claim bundle needs at least one claim")
    claims = [SemanticClaim.from_dict(item) for item in value["claims"]]
    if len({claim.id for claim in claims}) != len(claims):
        raise ValueError("Claim IDs must be unique")
    return selection, claims


def _transcript(source_id: str, transcripts: Mapping[str, Transcript]) -> Transcript:
    transcript = transcripts.get(source_id)
    if not isinstance(transcript, Transcript) or transcript.source_id != source_id:
        raise ValueError("Missing or mismatched canonical transcript")
    return transcript


def export_manifest(private_bundle: dict, transcripts: Mapping[str, Transcript]) -> dict:
    """Validate private annotations, then replace their quotes with verified offsets."""
    selection, claims = _private_bundle(private_bundle)
    public, sources = [], {}
    for claim in claims:
        transcript = _transcript(claim.source_id, transcripts)
        prepare_state(claim, transcript)
        sources[claim.source_id] = _source(transcript)
        segments = {segment.id: segment for segment in transcript.segments}
        item = claim.to_dict()

        def references(field: dict) -> dict:
            refs = []
            for evidence in field["evidence"]:
                segment = segments[evidence["segment_id"]]
                quote = evidence["quote"]
                start = segment.text.index(quote)
                refs.append({"segment_id": segment.id, "start_char": start, "end_char": start + len(quote),
                             "quote_sha256": hashlib.sha256(quote.encode("utf-8")).hexdigest(),
                             "start_seconds": segment.start, "end_seconds": segment.end})
            return {"value": field["value"], "evidence": refs}

        for name in FIELD_NAMES:
            item[name] = references(item[name])
        for name in LIST_FIELD_NAMES:
            item[name] = [references(field) for field in item[name]]
        public.append(item)
    return {"schema_version": 1, "format": FORMAT, "selection_basis": selection,
            "sources": sources, "claims": public}


def _hydrate(value: dict, transcripts: Mapping[str, Transcript]) -> tuple[str, list[SemanticClaim]]:
    _exact(value, {"schema_version", "format", "selection_basis", "sources", "claims"}, "public claim manifest")
    if value["format"] != FORMAT or type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise ValueError("Unsupported claim manifest format")
    if not isinstance(value["sources"], dict) or not value["sources"]:
        raise ValueError("A public manifest needs source hashes")
    if not isinstance(value["claims"], list) or not value["claims"]:
        raise ValueError("A public manifest needs claims")
    for source_id, source in value["sources"].items():
        transcript = _transcript(source_id, transcripts)
        if source != _source(transcript):
            raise ValueError("Canonical transcript hash or metadata differs from the manifest")
    hydrated = []
    used = set()
    for original in value["claims"]:
        if not isinstance(original, dict) or not isinstance(original.get("source_id"), str):
            raise ValueError("Claim source ID is missing")
        source_id = original["source_id"]
        if source_id not in value["sources"]:
            raise ValueError("A claim has no pinned source")
        used.add(source_id)
        transcript = _transcript(source_id, transcripts)
        segments = {segment.id: segment for segment in transcript.segments}
        item = deepcopy(original)

        def quotes(field: Any) -> dict:
            _exact(field, {"value", "evidence"}, "public grounded field")
            if not isinstance(field["evidence"], list):
                raise ValueError("Evidence references must be an array")
            evidence = []
            for ref in field["evidence"]:
                _exact(ref, {"segment_id", "start_char", "end_char", "quote_sha256",
                             "start_seconds", "end_seconds"}, "evidence reference")
                if not isinstance(ref["segment_id"], str) or ref["segment_id"] not in segments:
                    raise ValueError("Evidence segment is missing")
                segment = segments[ref["segment_id"]]
                start, end = ref["start_char"], ref["end_char"]
                if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(segment.text):
                    raise ValueError("Invalid evidence character offsets")
                if ref["start_seconds"] != segment.start or ref["end_seconds"] != segment.end:
                    raise ValueError("Evidence timestamps differ from the canonical segment")
                quote = segment.text[start:end]
                digest = ref["quote_sha256"]
                if (not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None
                        or hashlib.sha256(quote.encode("utf-8")).hexdigest() != digest):
                    raise ValueError("Evidence substring hash mismatch")
                evidence.append({"segment_id": segment.id, "quote": quote})
            return {"value": field["value"], "evidence": evidence}

        for name in FIELD_NAMES:
            if name not in item:
                raise ValueError("Claim field is missing")
            item[name] = quotes(item[name])
        for name in LIST_FIELD_NAMES:
            if not isinstance(item.get(name), list):
                raise ValueError("Claim list field is missing")
            item[name] = [quotes(field) for field in item[name]]
        hydrated.append(item)
    if used != set(value["sources"]):
        raise ValueError("Manifest source hashes must match the claimed sources exactly")
    selection, claims = _private_bundle({"schema_version": 1, "selection_basis": value["selection_basis"],
                                         "claims": hydrated})
    for claim in claims:
        prepare_state(claim, _transcript(claim.source_id, transcripts))
    return selection, claims


def load_manifest(path: str | Path, transcripts: Mapping[str, Transcript]) -> tuple[str, list[SemanticClaim]]:
    """Hydrate quote references only after matching the full canonical transcript hash."""
    return _hydrate(_read(path), transcripts)


def load_review_inputs(path: str | Path, transcript_dir: str | Path) -> tuple[str, list[SemanticClaim], dict[str, Transcript]]:
    """Load either private annotations or a public manifest with local canonical captions."""
    value = _read(path)
    is_manifest = "format" in value
    if is_manifest:
        if not isinstance(value.get("claims"), list) or not value["claims"]:
            raise ValueError("A public manifest needs claims")
        if any(not isinstance(item, dict) or not isinstance(item.get("source_id"), str) for item in value["claims"]):
            raise ValueError("Claim source ID is missing")
        ids = {item["source_id"] for item in value["claims"]}
    else:
        _, parsed = _private_bundle(value)
        ids = {claim.source_id for claim in parsed}
    root = Path(transcript_dir).resolve()
    transcripts = {}
    for source_id in sorted(ids):
        target = (root / f"{source_id}.json").resolve()
        if target.parent != root:
            raise ValueError("Source ID must identify a file directly inside the transcript directory")
        transcript = load_transcript(target)
        if transcript.source_id != source_id:
            raise ValueError("Transcript filename and canonical source ID disagree")
        transcripts[source_id] = transcript
    selection, claims = _hydrate(value, transcripts) if is_manifest else _private_bundle(value)
    for claim in claims:
        prepare_state(claim, transcripts[claim.source_id])
    return selection, claims, transcripts
