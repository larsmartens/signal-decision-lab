"""Study-boundary checks using only artificial captions and artificial prices."""
from contextlib import redirect_stdout
from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import csv
from io import StringIO
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from signal_lab.cli import main
from signal_lab.ingest import read_json, write_json
from signal_lab.krown_extract import BIAS_CONFIGS, RULE_WEIGHT
from signal_lab.krown_study import (
    CHANNEL_ID, extract_study_features, file_sha256, load_study_inputs, run_study, validate_features,
)
from signal_lab.models import jsonable
from signal_lab.research_backtest import run_research_backtest


T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
PRIVATE_TEXT = (
    "For Bitcoin, I am bullish today. For Bitcoin, I expect higher prices tomorrow. "
    "UniquelySyntheticCaptionMarker must stay in the private caption file."
)


def at(hours):
    return jsonable(T0 + timedelta(hours=hours))


def all_keys(value):
    if isinstance(value, dict):
        for key, item in value.items():
            yield key
            yield from all_keys(item)
    elif isinstance(value, list):
        for item in value:
            yield from all_keys(item)


class StudyBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.study_dir, self.transcripts = self.root / "study", self.root / "private-captions"
        self.study_dir.mkdir()
        self.transcripts.mkdir()
        entries, acquired = [], []
        for identifier, split, offset in (("synthetic01", "development", 0), ("synthetic02", "holdout", 72)):
            source = {"source_id": identifier, "url": f"https://www.youtube.com/watch?v={identifier}",
                      "channel_id": CHANNEL_ID, "split": split, "content_type": "normal_video",
                      "duration_seconds": 300, "published_at": at(offset),
                      "research_available_at": at(offset + 1 / 3)}
            entries.append(source)
            path = self.transcripts / f"{identifier}.json"
            write_json(path, {"source_id": identifier, "channel": "Synthetic test fixture", "url": source["url"],
                              "published_at": source["published_at"], "available_at": at(240), "kind": "synthetic",
                              "segments": [{"id": "s1", "start": 0, "end": 20, "text": PRIVATE_TEXT}]})
            acquired.append({"source_id": identifier, "status": "success", "retrieved_at": at(240),
                             "transcript_sha256": file_sha256(path)})
        self.sources = {"schema_version": 1, "study_id": "synthetic-study", "channel_id": CHANNEL_ID,
                        "market_cutoff": at(144), "entries": entries}
        self.acquisition = {"entries": acquired}
        write_json(self.study_dir / "sources.json", self.sources)
        write_json(self.study_dir / "acquisition.json", self.acquisition)
        with (self.study_dir / "market-bars.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=("asset", "open_time", "close_time", "open", "high",
                                                       "low", "close", "volume"))
            writer.writeheader()
            for i in range(-24, 144):
                opn, close = 100 + i / 20, 100 + (i + 1) / 20
                writer.writerow({"asset": "BTCUSDT", "open_time": at(i), "close_time": at(i + 1),
                                 "open": opn, "high": close, "low": opn, "close": close, "volume": 1})
        self.protocol = {
            "schema_version": 1, "study_id": "synthetic-study", "channel_id": CHANNEL_ID,
            "extractors": jsonable({key: asdict(value) for key, value in BIAS_CONFIGS.items()}),
            "rule_weights": RULE_WEIGHT,
            "splits": {"development": {"sample_start": at(0), "sample_end": at(72), "expected_sources": 1},
                       "holdout": {"sample_start": at(72), "sample_end": at(144), "expected_sources": 1}},
            "variants": [
                {"id": "lexical_24h", "label": "Synthetic lexical", "extractor": "lexical",
                 "holding_hours": 24, "confirmation": "none"},
                {"id": "standard_24h", "label": "Synthetic standard", "extractor": "context_standard",
                 "holding_hours": 24, "confirmation": "none"},
                {"id": "standard_48h", "label": "Synthetic 48-hour", "extractor": "context_standard",
                 "holding_hours": 48, "confirmation": "none"},
                {"id": "standard_breakout", "label": "Synthetic breakout", "extractor": "context_standard",
                 "holding_hours": 24, "confirmation": "breakout"},
            ],
            "engine": {"asset": "BTCUSDT", "initial_equity": 10_000.0, "max_signal_age_hours": 24.0,
                       "direction_mode": "long_short", "breakout_lookback_hours": 24,
                       "confirmation_window_hours": 24.0, "exposure_fraction": 1.0, "min_strength": 0.0},
            "costs": {"base": {"fee_bps": 10.0, "slippage_bps": 5.0},
                      "stress": {"fee_bps": 20.0, "slippage_bps": 10.0}},
            "model_runs": {"jev": {"status": "not_run"}, "llm_extraction": {"status": "not_run"}},
        }
        self.reseal_inputs()

    def reseal_inputs(self):
        self.protocol["input_sha256"] = {
            key: file_sha256(self.study_dir / name) for key, name in
            (("sources", "sources.json"), ("acquisition", "acquisition.json"), ("market_bars", "market-bars.csv"))}
        write_json(self.study_dir / "protocol.json", self.protocol)
        self.protocol_hash = file_sha256(self.study_dir / "protocol.json")
        self.freeze = {"schema_version": 1, "study_id": "synthetic-study", "protocol_sha256": self.protocol_hash,
                       "extractor_code_sha256": file_sha256(Path(__file__).parents[1] / "signal_lab/krown_extract.py")}
        write_json(self.study_dir / "extractor-freeze.json", self.freeze)

    def features(self):
        return extract_study_features(self.protocol, self.sources, self.acquisition,
                                      self.transcripts, self.protocol_hash)

    def validate(self, features):
        validate_features(features, self.protocol, self.sources, self.protocol_hash, self.freeze)

    def publish_synthetic_features(self, out):
        result = run_study(self.study_dir, out, transcript_dir=self.transcripts)
        for name in ("features.json", "feature-receipt.json"):
            shutil.copyfile(out / name, self.study_dir / name)
        return result

    def test_changed_source_acquisition_or_market_bytes_fail_the_frozen_hash_boundary(self):
        for filename in ("sources.json", "acquisition.json", "market-bars.csv"):
            with self.subTest(filename=filename):
                path = self.study_dir / filename
                original = path.read_bytes()
                path.write_bytes(original + b"\n")
                with self.assertRaisesRegex(ValueError, "checksum mismatch"):
                    load_study_inputs(self.study_dir)
                path.write_bytes(original)

    def test_reconstructed_clock_is_checked_even_after_rehashing_source_file(self):
        self.sources["entries"][0]["research_available_at"] = at(1)
        write_json(self.study_dir / "sources.json", self.sources)
        self.reseal_inputs()
        with self.assertRaisesRegex(ValueError, "availability"):
            load_study_inputs(self.study_dir)

    def test_duplicate_source_cannot_appear_in_two_cohorts(self):
        self.sources["entries"][1]["source_id"] = self.sources["entries"][0]["source_id"]
        write_json(self.study_dir / "sources.json", self.sources)
        self.reseal_inputs()
        with self.assertRaisesRegex(ValueError, "only one cohort"):
            load_study_inputs(self.study_dir)

    def test_cohort_window_overlap_is_rejected_with_valid_source_clocks(self):
        self.protocol["splits"]["development"]["sample_end"] = at(73)
        self.reseal_inputs()
        with self.assertRaisesRegex(ValueError, "windows overlap"):
            load_study_inputs(self.study_dir)

    def test_every_selected_source_requires_exactly_one_row_per_extractor(self):
        original = self.features()
        for mutation in (lambda value: value["records"].pop(),
                         lambda value: value["records"].append(deepcopy(value["records"][0]))):
            candidate = deepcopy(original)
            mutation(candidate)
            with self.assertRaises(ValueError):
                self.validate(candidate)

    def test_features_cannot_change_source_partition_or_availability(self):
        original = self.features()
        for key, value in (("split", "holdout"), ("available_at", at(1))):
            candidate = deepcopy(original)
            candidate["records"][0][key] = value
            with self.assertRaisesRegex(ValueError, "cohort or availability"):
                self.validate(candidate)

    def test_feature_extractor_provenance_must_match_the_frozen_code(self):
        candidate = self.features()
        candidate["extractor_code_sha256"] = "f" * 64
        with self.assertRaises(ValueError):
            self.validate(candidate)

    def test_public_feature_validation_rejects_caption_text_even_when_nested(self):
        original = self.features()
        for key in ("quote", "text", "caption_text", "full_text"):
            candidate = deepcopy(original)
            candidate["records"][0]["issues"] = [{"nested": [{key: PRIVATE_TEXT}]}]
            with self.subTest(key=key), self.assertRaises(ValueError):
                self.validate(candidate)
        candidate = deepcopy(original)
        candidate["literal_setup_coverage"][0]["issues"] = {"quote": PRIVATE_TEXT}
        with self.assertRaises(ValueError):
            self.validate(candidate)
        candidate = deepcopy(original)
        candidate["source_text_published"] = True
        with self.assertRaises(ValueError):
            self.validate(candidate)

    def test_extraction_exports_links_and_offsets_without_source_quotes(self):
        features = self.features()
        self.validate(features)
        encoded = json.dumps(features)
        self.assertNotIn("UniquelySyntheticCaptionMarker", encoded)
        self.assertNotIn("For Bitcoin, I am bullish today", encoded)
        self.assertFalse(set(all_keys(features)) & {"quote", "text", "caption_text", "full_text"})
        evidence = [span for row in features["records"] for span in row["evidence"]]
        self.assertTrue(evidence)
        self.assertTrue(all("&t=" in span["url"] and "segment_id" in span and "char_start" in span for span in evidence))

    def test_a_failed_caption_stays_in_all_variants_as_an_abstention(self):
        self.acquisition["entries"][0]["status"] = "failed"
        features = self.features()
        rows = [row for row in features["records"] if row["video_id"] == "synthetic01"]
        self.assertEqual(len(rows), len(BIAS_CONFIGS))
        self.assertTrue(all(row["direction"] == "flat" and row["strength"] == 0 for row in rows))
        self.assertTrue(all("caption_unavailable" in row["issues"] for row in rows))

    def test_changed_raw_captions_are_rejected_before_extraction(self):
        path = self.transcripts / "synthetic01.json"
        path.write_bytes(path.read_bytes() + b"\n")
        with self.assertRaisesRegex(ValueError, "Caption checksum mismatch"):
            self.features()

    def test_feature_receipt_is_written_before_any_simulation_and_replay_is_identical(self):
        fresh, replay = self.root / "fresh", self.root / "replay"

        def checked_simulation(*args, **kwargs):
            self.assertTrue((fresh / "features.json").is_file())
            self.assertTrue((fresh / "feature-receipt.json").is_file())
            return run_research_backtest(*args, **kwargs)

        with patch("signal_lab.krown_study.run_research_backtest", side_effect=checked_simulation), patch(
                "urllib.request.urlopen", side_effect=AssertionError("Synthetic study must stay offline")):
            first = self.publish_synthetic_features(fresh)
        second = run_study(self.study_dir, replay)
        self.assertEqual(first["results_sha256"], second["results_sha256"])
        self.assertEqual(first["strategy_runs"], 16)
        self.assertEqual(first["benchmark_runs"], 12)
        for name in ("summary.json", "features.json", "feature-receipt.json", "results.csv"):
            self.assertTrue((replay / name).is_file())
        summary = read_json(replay / "summary.json")
        for relative, digest in summary["files"].items():
            self.assertEqual(file_sha256(replay / relative), digest)
        self.assertFalse(summary["metadata"]["source_text_published"])
        self.assertEqual(summary["metadata"]["performance_scope"], "retrospective_directional_proxy")

    def test_saved_features_cannot_change_after_receipt_without_rejection(self):
        self.publish_synthetic_features(self.root / "fresh")
        features = read_json(self.study_dir / "features.json")
        features["records"][0]["direction"] = "short"
        write_json(self.study_dir / "features.json", features)
        with self.assertRaises(ValueError):
            run_study(self.study_dir, self.root / "tampered-replay")

    def test_shared_benchmark_guard_catches_a_source_variant_contaminated_control(self):
        def contaminated(events, bars, config):
            result = run_research_backtest(events, bars, config)
            if events[0]["variant"] == "context_standard" and config.holding_hours == 24:
                result["benchmarks"]["buy_and_hold"]["summary"]["net_pnl"] += 1
            return result

        with patch("signal_lab.krown_study.run_research_backtest", side_effect=contaminated):
            with self.assertRaisesRegex(ValueError, "shared benchmark differs"):
                run_study(self.study_dir, self.root / "inconsistent", transcript_dir=self.transcripts)

    def test_cli_replays_published_synthetic_features_without_provider_calls(self):
        self.publish_synthetic_features(self.root / "fresh")
        stream = StringIO()
        with redirect_stdout(stream), patch("signal_lab.cli.JevClient", side_effect=AssertionError("No model")), patch(
                "signal_lab.cli.LLMExtractor", side_effect=AssertionError("No model")), patch(
                "urllib.request.urlopen", side_effect=AssertionError("No network")):
            code = main(["krown-study", "--study-dir", str(self.study_dir), "--out", str(self.root / "cli"),
                         "--format", "json"])
        self.assertEqual(code, 0, stream.getvalue())
        response = json.loads(stream.getvalue())
        self.assertEqual(response["status"], "ok")
        self.assertEqual(response["model_calls"], 0)
        self.assertEqual(response["mode"], "directional-event-research")
        self.assertEqual(response["sources"], 2)


if __name__ == "__main__":
    unittest.main()
