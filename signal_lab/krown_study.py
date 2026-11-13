"""Frozen video cohorts, evidence references and reproducible research runs."""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import csv
import hashlib
import json
from pathlib import Path

from .extract import extract_rules
from .ingest import load_bars, load_transcript, read_json, write_json
from .krown_extract import (
    BIAS_CONFIGS, RULE_WEIGHT, BiasEvent, aggregate_bias, extract_bias_events, validate_bias_grounding,
)
from .models import jsonable, positive, utc
from .research_backtest import ResearchConfig, run_research_backtest


CHANNEL_ID = "UCnwxzpFzZNtLH8NgTeAROFA"


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_sha256(value: object) -> str:
    data = json.dumps(jsonable(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(data.encode()).hexdigest()


def _availability(source: dict) -> datetime:
    published = utc(source["published_at"])
    if source["content_type"] == "normal_video":
        positive(source["duration_seconds"], "duration_seconds")
        return published + timedelta(seconds=source["duration_seconds"], minutes=15)
    if source["content_type"] == "completed_livestream":
        return max(published, utc(source["live_end_at"])) + timedelta(minutes=15)
    raise ValueError("Study sources must be normal videos or completed livestreams")


def load_study_inputs(study_dir: Path) -> tuple[dict, dict, dict]:
    """Reject a changed input, cross-cohort ID or altered historical clock."""
    protocol = read_json(study_dir / "protocol.json")
    sources = read_json(study_dir / "sources.json")
    acquisition = read_json(study_dir / "acquisition.json")
    if protocol.get("schema_version") != 1 or sources.get("schema_version") != 1:
        raise ValueError("Study protocol and source manifest require schema_version=1")
    if protocol["study_id"] != sources["study_id"]:
        raise ValueError("Study identifiers do not match")
    for key, filename in (("sources", "sources.json"), ("acquisition", "acquisition.json"),
                          ("market_bars", "market-bars.csv")):
        if file_sha256(study_dir / filename) != protocol["input_sha256"][key]:
            raise ValueError(f"Frozen {key} checksum mismatch")
    if protocol["channel_id"] != CHANNEL_ID or sources["channel_id"] != CHANNEL_ID:
        raise ValueError("Study must use the verified Krown channel ID")
    if protocol["extractors"] != jsonable({key: asdict(value) for key, value in BIAS_CONFIGS.items()}):
        raise ValueError("Frozen extractor configuration differs from the installed implementation")
    if protocol["rule_weights"] != RULE_WEIGHT:
        raise ValueError("Frozen rule weights differ from the installed implementation")
    entries = sources["entries"]
    ids = [source["source_id"] for source in entries]
    if len(ids) != len(set(ids)):
        raise ValueError("A source may appear in only one cohort")
    acquired_ids = [item["source_id"] for item in acquisition["entries"]]
    if len(acquired_ids) != len(set(acquired_ids)) or set(ids) != set(acquired_ids):
        raise ValueError("Acquisition must record each selected source exactly once, including failures")
    for split, window in protocol["splits"].items():
        cohort = [source for source in entries if source["split"] == split]
        if len(cohort) != window["expected_sources"]:
            raise ValueError(f"Unexpected {split} cohort size")
        start, end = utc(window["sample_start"]), utc(window["sample_end"])
        for source in cohort:
            if source["channel_id"] != CHANNEL_ID:
                raise ValueError("Source belongs to another channel")
            available = _availability(source)
            if available != utc(source["research_available_at"]):
                raise ValueError("Reconstructed availability does not follow the frozen rule")
            if not start <= available < end:
                raise ValueError("Source clock lies outside its cohort window")
    if any(source["split"] not in protocol["splits"] for source in entries):
        raise ValueError("Unknown source cohort")
    windows = sorted(protocol["splits"].values(), key=lambda value: value["sample_start"])
    if any(utc(left["sample_end"]) > utc(right["sample_start"]) for left, right in zip(windows, windows[1:])):
        raise ValueError("Cohort trading windows overlap")
    return protocol, sources, acquisition


def _span_reference(span, source: dict) -> dict:
    # Whitelist fields; source text cannot reach the public output through an extra field.
    return {"segment_id": span.segment_id, "start_seconds": span.start_seconds,
            "end_seconds": span.end_seconds, "char_start": span.char_start,
            "char_end": span.char_end,
            "url": f"{source['url']}&t={int(span.start_seconds)}s"}


def extract_study_features(protocol: dict, sources: dict, acquisition: dict,
                           transcript_dir: Path, protocol_sha256: str) -> dict:
    """Read canonical captions once, validate evidence, export numeric views and offsets."""
    acquired = {item["source_id"]: item for item in acquisition["entries"]}
    records, literal = [], []
    for source in sources["entries"]:
        identifier = source["source_id"]
        receipt = acquired[identifier]
        transcript = None
        if receipt["status"] == "success":
            path = transcript_dir / f"{identifier}.json"
            if file_sha256(path) != receipt["transcript_sha256"]:
                raise ValueError(f"Caption checksum mismatch for {identifier}")
            transcript = load_transcript(path)
            if transcript.source_id != identifier or transcript.url != source["url"]:
                raise ValueError("Caption identity does not match the selected source")
            if transcript.published_at != utc(source["published_at"]):
                raise ValueError("Caption publication metadata differs from the selected source")
            if transcript.available_at != utc(receipt["retrieved_at"]):
                raise ValueError("Canonical caption availability must remain its actual retrieval time")
            claims = extract_rules(transcript)
            literal.append({"video_id": identifier, "split": source["split"], "status": "success",
                            "asset_mentions": len(claims),
                            "complete_supported_setups": sum(not claim.issues for claim in claims),
                            "reviewed": sum(claim.reviewed for claim in claims),
                            "issues": dict(Counter(issue for claim in claims for issue in claim.issues))})
        else:
            literal.append({"video_id": identifier, "split": source["split"],
                            "status": "caption_unavailable", "asset_mentions": 0,
                            "complete_supported_setups": 0, "reviewed": 0, "issues": {}})
        for extractor in protocol["extractors"]:
            events = extract_bias_events(transcript, extractor) if transcript else []
            if transcript:
                for event in events:
                    validate_bias_grounding(event, transcript)
            summary = aggregate_bias(events, extractor, video_id=identifier)
            public = jsonable(summary)
            public["evidence"] = [_span_reference(span, source) for span in summary.evidence]
            if transcript is None:
                public["issues"].append("caption_unavailable")
            accepted: dict[tuple[str, str], BiasEvent] = {}
            for event in events:
                if event.accepted:
                    key = event.unit_id, event.direction
                    if key not in accepted or event.strength > accepted[key].strength:
                        accepted[key] = event
            public["accepted_units"] = [
                {"id": event.id, "unit_id": event.unit_id, "direction": event.direction,
                 "rule": event.rule, "weight": event.strength,
                 "timeframe_minutes": event.timeframe_minutes, "horizon_minutes": event.horizon_minutes,
                 "derivatives_mentioned": event.derivatives_mentioned,
                 "evidence": [_span_reference(span, source) for span in event.evidence]}
                for event in accepted.values()
            ]
            public.update({"split": source["split"], "available_at": source["research_available_at"],
                           "actual_retrieved_at": receipt.get("retrieved_at"),
                           "transcript_sha256": receipt.get("transcript_sha256"),
                           "caption_status": receipt["status"], "asset": protocol["engine"]["asset"]})
            records.append(public)
    return {"schema_version": 1, "study_id": protocol["study_id"],
            "protocol_sha256": protocol_sha256, "input_sha256": protocol["input_sha256"],
            "extractor_code_sha256": file_sha256(Path(__file__).with_name("krown_extract.py")),
            "score_kind": "heuristic_directional_balance_not_probability",
            "source_text_published": False, "records": records, "literal_setup_coverage": literal}


def _public_fields(value: dict, allowed: set[str]) -> None:
    if set(value) - allowed:
        raise ValueError(f"Unknown public feature fields (source text is not allowed): {sorted(set(value) - allowed)}")


def _reject_source_text(value: object) -> None:
    if isinstance(value, dict):
        if {"quote", "text", "caption_text", "full_text"} & value.keys():
            raise ValueError("Public features cannot contain caption text or quotes")
        for child in value.values():
            _reject_source_text(child)
    elif isinstance(value, list):
        for child in value:
            _reject_source_text(child)


def validate_features(features: dict, protocol: dict, sources: dict, protocol_sha256: str, freeze: dict) -> None:
    _reject_source_text(features)
    _public_fields(features, {"schema_version", "study_id", "protocol_sha256", "input_sha256",
                             "extractor_code_sha256", "score_kind", "source_text_published",
                             "records", "literal_setup_coverage"})
    if features.get("schema_version") != 1 or features.get("study_id") != protocol["study_id"]:
        raise ValueError("Features do not belong to this study")
    if features.get("source_text_published") is not False:
        raise ValueError("Public features must exclude caption text")
    if features["extractor_code_sha256"] != freeze["extractor_code_sha256"]:
        raise ValueError("Feature extractor provenance differs from the code freeze")
    if features["protocol_sha256"] != protocol_sha256 or features["input_sha256"] != protocol["input_sha256"]:
        raise ValueError("Features do not match the frozen input and policy hashes")
    source_by_id = {source["source_id"]: source for source in sources["entries"]}
    expected = {(identifier, variant) for identifier in source_by_id for variant in protocol["extractors"]}
    seen = set()
    for row in features["records"]:
        _public_fields(row, {"video_id", "variant", "direction", "strength", "signed_score", "supporting_count",
                             "conflicting_count", "excluded_count", "evidence", "issues", "counts_by_reason",
                             "positive_count", "negative_count", "extractor", "score_kind", "accepted_units",
                             "split", "available_at", "actual_retrieved_at", "transcript_sha256", "caption_status", "asset"})
        references = list(row.get("evidence", []))
        for unit in row.get("accepted_units", []):
            _public_fields(unit, {"id", "unit_id", "direction", "rule", "weight", "timeframe_minutes",
                                  "horizon_minutes", "derivatives_mentioned", "evidence"})
            references.extend(unit["evidence"])
        for span in references:
            _public_fields(span, {"segment_id", "start_seconds", "end_seconds", "char_start", "char_end", "url"})
        key = row["video_id"], row["variant"]
        if key in seen or key not in expected:
            raise ValueError("Duplicate or unselected source feature")
        seen.add(key)
        source = source_by_id[row["video_id"]]
        if row["split"] != source["split"] or utc(row["available_at"]) != utc(source["research_available_at"]):
            raise ValueError("Feature has changed its source cohort or availability")
        if row["asset"] != protocol["engine"]["asset"] or row["direction"] not in {"long", "short", "flat"}:
            raise ValueError("Invalid source direction or market mapping")
        positive(row["strength"], "strength", zero=True)
        if row["strength"] > 1 or (row["direction"] == "flat" and row["strength"] != 0):
            raise ValueError("Invalid heuristic strength")
    if seen != expected:
        raise ValueError("Every selected source requires every extractor, including abstentions")
    for row in features["literal_setup_coverage"]:
        _public_fields(row, {"video_id", "split", "status", "asset_mentions", "complete_supported_setups", "reviewed", "issues"})


def _write_compact(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(jsonable(value), ensure_ascii=False, allow_nan=False,
                               separators=(",", ":")) + "\n", encoding="utf-8")


def run_study(study_dir: Path, out: Path, *, transcript_dir: Path | None = None,
              charts_out: Path | None = None) -> dict:
    protocol, sources, acquisition = load_study_inputs(study_dir)
    protocol_hash = file_sha256(study_dir / "protocol.json")
    freeze = read_json(study_dir / "extractor-freeze.json")
    if freeze["protocol_sha256"] != protocol_hash:
        raise ValueError("Extractor freeze belongs to a different protocol")
    if transcript_dir is not None:
        actual = file_sha256(Path(__file__).with_name("krown_extract.py"))
        if freeze["extractor_code_sha256"] != actual:
            raise ValueError("Freeze the final extractor code before processing holdout captions")
        features = extract_study_features(protocol, sources, acquisition, transcript_dir, protocol_hash)
    else:
        features = read_json(study_dir / "features.json")
        receipt = read_json(study_dir / "feature-receipt.json")
        if receipt["features_sha256"] != file_sha256(study_dir / "features.json"):
            raise ValueError("Frozen feature checksum mismatch")
        if receipt["protocol_sha256"] != protocol_hash or receipt["extractor_code_sha256"] != freeze["extractor_code_sha256"]:
            raise ValueError("Feature receipt does not match the frozen protocol and extractor")
    validate_features(features, protocol, sources, protocol_hash, freeze)
    # The feature snapshot is written before any backtest is evaluated.
    _write_compact(out / "features.json", features)
    if transcript_dir is not None:
        receipt = {"schema_version": 1, "study_id": protocol["study_id"],
                   "frozen_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                   "features_sha256": file_sha256(out / "features.json"),
                   "protocol_sha256": protocol_hash, "extractor_code_sha256": freeze["extractor_code_sha256"],
                   "frozen_before_backtest": True}
    write_json(out / "feature-receipt.json", receipt)
    bars = load_bars(study_dir / "market-bars.csv")
    if bars[-1].close_time > utc(sources["market_cutoff"]) or bars[-1].close_time > datetime.now(timezone.utc):
        raise ValueError("Market data extends past the declared cutoff or includes an incomplete future candle")
    coverage = []
    for split in protocol["splits"]:
        for extractor in protocol["extractors"]:
            rows = [row for row in features["records"] if row["split"] == split and row["variant"] == extractor]
            counts = Counter(row["direction"] for row in rows)
            coverage.append({"split": split, "extractor": extractor, "videos": len(rows),
                             "long": counts["long"], "short": counts["short"], "flat": counts["flat"],
                             "caption_failures": sum(row["caption_status"] != "success" for row in rows)})
    result_rows: list[dict] = []
    runs: dict[str, dict] = {}
    benchmarks: dict[str, dict] = {}
    files: dict[str, str] = {}
    for split, window in protocol["splits"].items():
        for variant in protocol["variants"]:
            source_features = [row for row in features["records"]
                               if row["split"] == split and row["variant"] == variant["extractor"]]
            for cost, charges in protocol["costs"].items():
                config = ResearchConfig(**protocol["engine"], **charges,
                                        holding_hours=variant["holding_hours"], confirmation=variant["confirmation"],
                                        sample_start=window["sample_start"], sample_end=window["sample_end"])
                events = [{key: row[key] for key in ("video_id", "available_at", "direction", "strength", "variant", "asset")}
                          for row in source_features]
                result = run_research_backtest(events, bars, config)
                run_id = f"{split}__{variant['id']}__{cost}"
                runs[run_id] = result
                result_rows.append({"run_id": run_id, "split": split, "variant": variant["id"],
                                    "label": variant["label"], "extractor": variant["extractor"], "cost": cost,
                                    "holding_hours": variant["holding_hours"], "confirmation": variant["confirmation"],
                                    **result["summary"]})
                refs = {}
                for name, benchmark in result["benchmarks"].items():
                    suffix = "" if name == "buy_and_hold" else f"__{variant['holding_hours']}h"
                    benchmark_id = f"{split}__{name}{suffix}__{cost}"
                    # A control is calculated for each run and checked before deduplicating storage.
                    if benchmark_id in benchmarks:
                        previous = benchmarks[benchmark_id]
                        for field in ("summary", "equity", "drawdown", "trades"):
                            if previous[field] != benchmark[field]:
                                raise ValueError("A supposedly shared benchmark differs between variants")
                    else:
                        benchmarks[benchmark_id] = benchmark
                    refs[name] = f"../benchmarks/{benchmark_id}.json"
                saved = {key: value for key, value in result.items() if key != "benchmarks"}
                saved["benchmark_files"] = refs
                relative = f"runs/{run_id}.json"
                _write_compact(out / relative, saved)
                files[relative] = file_sha256(out / relative)
    for identifier, benchmark in benchmarks.items():
        relative = f"benchmarks/{identifier}.json"
        _write_compact(out / relative, benchmark)
        files[relative] = file_sha256(out / relative)
    metadata = {"source_count": len(sources["entries"]),
                "caption_successes": sum(row["status"] == "success" for row in acquisition["entries"]),
                "total_duration_hours": sum(source["duration_seconds"] for source in sources["entries"]) / 3600,
                "source_channel": "Krown / @ECKrown", "market": "Binance spot BTCUSDT", "market_bars": len(bars),
                "protocol_sha256": protocol_hash, "feature_sha256": file_sha256(out / "features.json"),
                "input_sha256": protocol["input_sha256"],
                "extractor_code_sha256": features["extractor_code_sha256"],
                "engine_code_sha256": file_sha256(Path(__file__).with_name("research_backtest.py")),
                "runner_code_sha256": file_sha256(Path(__file__)),
                "model_runs": protocol["model_runs"], "windows": protocol["splits"],
                "source_text_published": False, "performance_scope": "retrospective_directional_proxy"}
    diagnostics_path = study_dir / "diagnostics.json"
    if diagnostics_path.is_file():
        metadata["post_outcome_diagnostics"] = read_json(diagnostics_path)
        metadata["diagnostics_sha256"] = file_sha256(diagnostics_path)
    benchmark_rows = [{"benchmark_id": identifier, **result["summary"]} for identifier, result in benchmarks.items()]
    study = {"schema_version": 1, "study_id": protocol["study_id"], "metadata": metadata,
             "coverage": coverage, "rows": result_rows, "benchmark_rows": benchmark_rows,
             "literal_setup_coverage": features["literal_setup_coverage"], "files": files}
    with (out / "results.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(result_rows[0]))
        writer.writeheader()
        writer.writerows(result_rows)
    by_source = {source["source_id"]: source for source in sources["entries"]}
    view_rows = []
    for row in features["records"]:
        source = by_source[row["video_id"]]
        view_rows.append({"video_id": row["video_id"], "split": row["split"], "title": source.get("title", ""),
                          "content_type": source["content_type"], "published_at": source["published_at"],
                          "research_available_at": row["available_at"], "extractor": row["variant"],
                          **{key: row[key] for key in ("direction", "strength", "signed_score", "supporting_count",
                                                      "conflicting_count", "excluded_count", "caption_status")},
                          "evidence_url": row["evidence"][0]["url"] if row["evidence"] else source["url"]})
    with (out / "source-views.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(view_rows[0]))
        writer.writeheader()
        writer.writerows(view_rows)
    trade_rows = [{"run_id": identifier, **trade} for identifier, result in runs.items() for trade in result["trades"]]
    with (out / "trades.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(trade_rows[0]) if trade_rows else ["run_id"])
        writer.writeheader()
        writer.writerows(trade_rows)
    for relative in ("features.json", "feature-receipt.json", "results.csv", "source-views.csv", "trades.csv"):
        files[relative] = file_sha256(out / relative)
    write_json(out / "summary.json", study)
    chart_paths = []
    if charts_out is not None:
        from .krown_charts import render_study_charts
        chart_paths = render_study_charts({**study, "runs": runs}, sources, charts_out)
    return {"status": "ok", "study_id": protocol["study_id"], "mode": "directional-event-research",
            "sources": len(sources["entries"]), "strategy_runs": len(runs), "benchmark_runs": len(benchmarks),
            "results_sha256": canonical_sha256(result_rows), "summary": str((out / "summary.json").resolve()),
            "charts": chart_paths, "model_calls": 0}
