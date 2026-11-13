"""Non-interactive research commands with compact TOON or explicit JSON output."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys

from .engine import Policy
from .evaluate import calibration_report
from .extract import extract_rules, review_signal, validate_grounding
from .ingest import fetch_youtube, load_bars, load_transcript, read_json, transcribe_media, write_json
from .jev import MODEL, JevClient
from .llm import LLMExtractor
from .models import Signal, Transcript, jsonable, strict_keys, utc
from .replay import run_replay
from .report import render_report


class UsageError(ValueError):
    pass


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise UsageError(f"{message}. Run {self.prog} --help for valid flags.")


def _format_argument(parser, *, sub=False):
    parser.add_argument("--format", choices=("toon", "json"), default=argparse.SUPPRESS if sub else "toon", help="Structured stdout format (default: toon)")


def parser() -> Parser:
    root = Parser(prog="signal-lab", description="Evidence-preserving transcript signals and paper simulation. No live order execution.")
    _format_argument(root)
    commands = root.add_subparsers(dest="command")
    demo = commands.add_parser("demo", help="Run the complete offline synthetic scenario")
    demo.add_argument("--out", default="artifacts/demo", help="Output directory")
    demo.add_argument("--judge", choices=("rules", "jev"), default="rules", help="Optional Jev paper experiment; default: rules")
    extract = commands.add_parser("extract", help="Extract unreviewed claims from JSON/VTT/SRT")
    extract.add_argument("input")
    extract.add_argument("--metadata", help="Required sidecar JSON for VTT/SRT")
    extract.add_argument("--provider", choices=("rules", "llm"), default="rules")
    extract.add_argument("--as-of", help="Explicit historical processing timestamp assumption; default actual completion time")
    extract.add_argument("--out", required=True)
    review = commands.add_parser("review", help="Record explicit approval of one evidence-checked signal")
    review.add_argument("--input", required=True)
    review.add_argument("--signal", required=True)
    review.add_argument("--reviewer", required=True)
    review.add_argument("--reviewed-at", help="Approval timestamp; default now")
    review.add_argument("--out", required=True)
    replay = commands.add_parser("replay", help="Chronological paper replay of reviewed evidence")
    replay.add_argument("--signals", required=True)
    replay.add_argument("--bars", required=True)
    replay.add_argument("--policy", help="Optional policy JSON; unknown keys rejected")
    replay.add_argument("--judge", choices=("rules", "jev"), default="rules", help="Optional Jev paper experiment; default: rules")
    replay.add_argument("--out", required=True)
    replay.add_argument("--report", help="Optional self-contained HTML report path")
    youtube = commands.add_parser("import-youtube", help="Fetch available captions without inventing a historical ingestion time")
    youtube.add_argument("--url", required=True)
    youtube.add_argument("--channel", required=True)
    youtube.add_argument("--published-at", required=True, help="Verified original publication timestamp with offset")
    youtube.add_argument("--language", default="en")
    youtube.add_argument("--out", required=True)
    asr = commands.add_parser("transcribe", help="Transcribe a local audio/video file using optional CPU Whisper")
    asr.add_argument("input")
    asr.add_argument("--metadata", required=True)
    asr.add_argument("--model", default="small.en")
    asr.add_argument("--out", required=True)
    evaluate = commands.add_parser("evaluate", help="Measure decision calibration on labeled predictions")
    evaluate.add_argument("--predictions", required=True)
    evaluate.add_argument("--out", required=True)
    show = commands.add_parser("show", help="Inspect saved research records")
    show.add_argument("input")
    show.add_argument("--full", action="store_true")
    report = commands.add_parser("report", help="Render an existing replay bundle as HTML")
    report.add_argument("input")
    report.add_argument("--out", required=True)
    study = commands.add_parser("krown-study", help="Replay the frozen Krown video study without network or model calls")
    study.add_argument("--study-dir", default="experiments/krown-20261114", help="Frozen inputs and published features")
    study.add_argument("--out", default="artifacts/krown-replay", help="Output directory")
    study.add_argument("--transcripts", help="Re-extract from the exact acquired canonical captions instead of saved features")
    study.add_argument("--charts", help="Optional chart directory; requires the research extra")
    for child in (demo, extract, review, replay, youtube, asr, evaluate, show, report, study):
        _format_argument(child, sub=True)
    return root


def _emit(data: dict, output_format: str) -> None:
    data = jsonable(data)
    if output_format == "json":
        print(json.dumps(data, ensure_ascii=False, allow_nan=False))
        return
    # Compact home/command responses use scalar fields. Complex explicit --full
    # inspection uses JSON, which the caller selected through that detail path.
    for key, value in data.items():
        if isinstance(value, list) and all(isinstance(v, (str, int, float, bool)) or v is None for v in value):
            print(f"{key}[{len(value)}]: " + ",".join(json.dumps(v, ensure_ascii=False) for v in value))
        elif isinstance(value, (dict, list)):
            print(f"{key}: " + json.dumps(json.dumps(value, ensure_ascii=False), ensure_ascii=False))
        else:
            print(f"{key}: " + json.dumps(value, ensure_ascii=False))


def _bundle(path) -> tuple[dict, Transcript, list[Signal]]:
    bundle = read_json(path)
    if not isinstance(bundle, dict) or bundle.get("schema_version") != 1:
        raise ValueError("Expected a schema_version=1 extraction or replay bundle")
    transcript = Transcript.from_dict(bundle["transcript"])
    signals = [Signal.from_dict(s) for s in bundle["signals"]]
    for signal in signals:
        validate_grounding(signal, transcript)
    return bundle, transcript, signals


def _judge(name):
    if name == "jev":
        return JevClient(model=os.environ.get("TYPESAFE_MODEL", MODEL)).judge
    return None


def _manifest(bundle: dict) -> dict:
    text = json.dumps(jsonable(bundle), sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return {"sha256_canonical_payload": hashlib.sha256(text.encode()).hexdigest(), "schema_version": 1, "mode": "paper_only"}


def _summary(bundle, path) -> dict:
    signals = bundle.get("signals", [])
    summary = bundle.get("replay", {}).get("summary", {})
    result = {"status": "ok", "mode": "paper_only", "signals": len(signals), "reviewed": sum(s["reviewed"] for s in signals), "saved": str(Path(path).resolve())}
    for key in ("entries", "completed_trades", "model_calls", "final_equity", "net_pnl"):
        if key in summary:
            result[key] = summary[key]
    return result


def execute(args) -> dict:
    if args.command == "krown-study":
        from .krown_study import run_study
        return run_study(Path(args.study_dir), Path(args.out),
                         transcript_dir=Path(args.transcripts) if args.transcripts else None,
                         charts_out=Path(args.charts) if args.charts else None)
    if args.command is None:
        return {"bin": sys.executable, "description": "Transcript evidence, conditional setups and paper decisions", "mode": "paper_only", "live_orders": "not implemented", "help": ["python -m signal_lab demo", "python -m signal_lab extract --help", "python -m signal_lab replay --help"]}
    if args.command == "demo":
        examples = Path(__file__).resolve().parent.parent / "examples"
        if not (examples / "synthetic-transcript.json").is_file():
            examples = Path(sys.prefix) / "share/signal-decision-lab/examples"
        transcript = load_transcript(examples / "synthetic-transcript.json")
        signals = extract_rules(transcript)
        # Only synthetic fixtures receive automatic demonstration approval.
        if transcript.kind != "synthetic":
            raise ValueError("Demo auto-review requires explicitly synthetic source material")
        signals = [review_signal(s, transcript, reviewed_at=s.available_at) if not s.issues and s.statement_type == "conditional" and s.side == "long" else s for s in signals]
        result = run_replay(signals, load_bars(examples / "synthetic-bars.csv"), judge=_judge(args.judge))
        bundle = {"schema_version": 1, "transcript": jsonable(transcript), "signals": jsonable(signals), "replay": result, "review_log": [{"reviewer": "synthetic_demo_fixture", "scope": "synthetic scenarios only"}], "evaluation_scope": "Synthetic mechanics; not a historical Krown strategy or profit validation"}
        output = Path(args.out)
        write_json(output / "run.json", bundle)
        write_json(output / "manifest.json", _manifest(bundle))
        render_report(bundle, output / "report.html")
        return {**_summary(bundle, output / "run.json"), "report": str((output / "report.html").resolve()), "evidence": "synthetic scenario"}
    if args.command == "extract":
        transcript = load_transcript(args.input, args.metadata)
        at = utc(args.as_of) if args.as_of else None
        if args.provider == "llm":
            base, model = os.environ.get("SIGNAL_LLM_BASE_URL"), os.environ.get("SIGNAL_LLM_MODEL")
            if not base or not model:
                raise ValueError("Set SIGNAL_LLM_BASE_URL and SIGNAL_LLM_MODEL before selecting --provider llm")
            signals = LLMExtractor(base, model, os.environ.get("SIGNAL_LLM_API_KEY") or None).extract(transcript, extracted_at=at)
        else:
            signals = extract_rules(transcript, extracted_at=at or datetime.now(timezone.utc))
        bundle = {"schema_version": 1, "transcript": jsonable(transcript), "signals": jsonable(signals), "extraction_time_basis": "explicit_historical_assumption" if args.as_of else "actual_processing_time", "review_log": []}
        write_json(args.out, bundle)
        return {**_summary(bundle, args.out), "help": [f"python -m signal_lab show {args.out}"]}
    if args.command == "review":
        bundle, transcript, signals = _bundle(args.input)
        if not args.reviewer.strip():
            raise ValueError("reviewer must be a non-empty identity")
        matches = [s for s in signals if s.id == args.signal]
        if len(matches) != 1:
            raise ValueError("Signal ID not found uniquely; inspect with show")
        reviewed = review_signal(matches[0], transcript, reviewed_at=utc(args.reviewed_at) if args.reviewed_at else datetime.now(timezone.utc))
        bundle["signals"] = jsonable([reviewed if s.id == reviewed.id else s for s in signals])
        bundle.setdefault("review_log", []).append({"signal_id": reviewed.id, "reviewer": args.reviewer, "reviewed_at": jsonable(reviewed.available_at)})
        bundle.pop("replay", None)
        write_json(args.out, bundle)
        return _summary(bundle, args.out)
    if args.command == "replay":
        bundle, _, signals = _bundle(args.signals)
        config = read_json(args.policy) if args.policy else {}
        strict_keys(Policy, config)
        bundle["replay"] = run_replay(signals, load_bars(args.bars), Policy(**config), judge=_judge(args.judge))
        bundle["input_hashes"] = {"signals": hashlib.sha256(Path(args.signals).read_bytes()).hexdigest(), "bars": hashlib.sha256(Path(args.bars).read_bytes()).hexdigest()}
        write_json(args.out, bundle)
        if args.report:
            render_report(bundle, args.report)
        return _summary(bundle, args.out)
    if args.command in {"import-youtube", "transcribe"}:
        transcript = fetch_youtube(args.url, channel=args.channel, published_at=args.published_at, languages=(args.language,)) if args.command == "import-youtube" else transcribe_media(args.input, read_json(args.metadata), model=args.model)
        write_json(args.out, transcript)
        return {"status": "ok", "segments": len(transcript.segments), "available_at": jsonable(transcript.available_at), "saved": str(Path(args.out).resolve())}
    if args.command == "evaluate":
        report = calibration_report(read_json(args.predictions))
        write_json(args.out, report)
        return {key: value for key, value in report.items() if key != "buckets"} | {"saved": str(Path(args.out).resolve())}
    if args.command == "report":
        bundle = read_json(args.input)
        render_report(bundle, args.out)
        return {"status": "ok", "report": str(Path(args.out).resolve())}
    bundle = read_json(args.input)
    if args.full:
        return bundle if isinstance(bundle, dict) else {"records": bundle}
    records = bundle.get("signals", []) if isinstance(bundle, dict) else bundle
    return {"count": len(records), "records": [{k: s.get(k) for k in ("id", "asset", "statement_type", "reviewed")} for s in records[:100]], "help": [f"python -m signal_lab show {args.input} --full --format json"]}


def main(argv: list[str] | None = None) -> int:
    output_format = "toon"
    try:
        args = parser().parse_args(argv)
        output_format = args.format
        result = execute(args)
        _emit(result, "json" if getattr(args, "full", False) else output_format)
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        _emit({"status": "error", "error": str(exc), "help": "python -m signal_lab --help"}, output_format)
        return 2 if isinstance(exc, UsageError) else 1


if __name__ == "__main__":
    raise SystemExit(main())
