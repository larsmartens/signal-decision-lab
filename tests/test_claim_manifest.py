"""Public references must reconstruct exact local evidence without publishing captions."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from signal_lab.claim_manifest import export_manifest, load_manifest, load_review_inputs, transcript_sha256
from signal_lab.models import Evidence, Segment, Transcript, jsonable
from signal_lab.semantic_claims import GroundedField, SemanticClaim


ROOT = Path(__file__).resolve().parents[1]
CAPTURED = datetime(2026, 11, 13, 23, tzinfo=timezone.utc)


def fixture() -> tuple[dict, dict[str, Transcript]]:
    transcript = Transcript("synthetic-context", "Synthetic discussion", "https://example.com/synthetic",
                            CAPTURED, CAPTURED, (
        Segment("s1", 0, 10, "The preceding chart showed Bitcoin's volatility indicator."),
        Segment("s2", 10, 20, "À propos, Ethereum could advance toward 3200."),
        Segment("s3", 20, 30, "If it closes the day above 3000, that move becomes more likely."),
        Segment("s4", 30, 40, "A daily close below 2800 cancels that scenario."),
        Segment("s5", 40, 50, "I have not given a deadline for the move."),
    ), kind="synthetic")

    def field(value, segment, quote):
        return GroundedField(value, (Evidence(segment, quote),))

    claim = SemanticClaim(
        id="eth-conditional", source_id=transcript.source_id, first_segment_id="s2", last_segment_id="s5",
        ticker=field("ETH", "s2", "Ethereum"), stance="conditional",
        expected_move=field("A possible rise toward 3,200.", "s2", "could advance toward 3200."),
        conditions=(field("A daily close above 3,000.", "s3", "If it closes the day above 3000"),),
        invalidation=field("A daily close below 2,800.", "s4", "A daily close below 2800 cancels that scenario."),
        timeframe=GroundedField(None, ()), targets=(field("3,200", "s2", "3200"),),
        interpretation="The condition and cancellation apply to Ethereum. No move deadline is specified.",
        author_kind="assistant", author_name="Synthetic fixture author", created_at=CAPTURED,
    )
    return {"schema_version": 1, "selection_basis": "Synthetic evidence reference test.",
            "claims": [claim.to_dict()]}, {transcript.source_id: transcript}


def save(path: Path, value: dict) -> Path:
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
    return path


class ClaimManifestTests(unittest.TestCase):
    def test_export_omits_quotes_and_round_trip_preserves_all_interpretation_fields(self):
        private, transcripts = fixture()
        public = export_manifest(private, transcripts)
        serialized = json.dumps(public, ensure_ascii=False)
        self.assertNotIn('"quote":', serialized)
        self.assertNotIn("could advance toward 3200.", serialized)
        self.assertNotIn('"segments":', serialized)
        evidence = public["claims"][0]["ticker"]["evidence"][0]
        self.assertEqual(evidence["start_char"], len("À propos, "))
        self.assertEqual(evidence["end_char"], len("À propos, Ethereum"))
        self.assertEqual(evidence["start_seconds"], 10)
        source_id = private["claims"][0]["source_id"]
        self.assertEqual(public["sources"][source_id]["canonical_transcript_sha256"],
                         transcript_sha256(transcripts[source_id]))
        with tempfile.TemporaryDirectory() as directory:
            path = save(Path(directory) / "claims.json", public)
            selection, restored = load_manifest(path, transcripts)
        self.assertEqual(selection, private["selection_basis"])
        self.assertEqual(restored[0].to_dict(), private["claims"][0])
        self.assertEqual(private["claims"][0]["ticker"]["evidence"][0]["quote"], "Ethereum")

    def test_changed_uncited_caption_or_capture_metadata_rejects_the_whole_source(self):
        private, transcripts = fixture()
        public = export_manifest(private, transcripts)
        original = transcripts["synthetic-context"]
        changed_text = replace(original, segments=(replace(original.segments[0], text="A different introduction."),
                                                    *original.segments[1:]))
        changed_time = replace(original, available_at=CAPTURED.replace(minute=1))
        with tempfile.TemporaryDirectory() as directory:
            path = save(Path(directory) / "claims.json", public)
            for altered in (changed_text, changed_time):
                with self.subTest(altered=altered), self.assertRaisesRegex(ValueError, "hash or metadata"):
                    load_manifest(path, {original.source_id: altered})

    def test_tampered_offsets_hashes_times_and_caption_text_are_rejected(self):
        private, transcripts = fixture()
        public = export_manifest(private, transcripts)
        mutations = ({"start_char": 0}, {"end_char": 9999}, {"start_char": True},
                     {"quote_sha256": "0" * 64}, {"start_seconds": 11}, {"quote": "unwanted caption text"})
        with tempfile.TemporaryDirectory() as directory:
            for mutation in mutations:
                altered = deepcopy(public)
                altered["claims"][0]["ticker"]["evidence"][0].update(mutation)
                path = save(Path(directory) / "claims.json", altered)
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    load_manifest(path, transcripts)

    def test_missing_source_and_ungrounded_private_annotations_cannot_be_exported(self):
        private, transcripts = fixture()
        with self.assertRaises(ValueError):
            export_manifest(private, {})
        private["claims"][0]["ticker"]["evidence"][0]["quote"] = "not present in the transcript"
        with self.assertRaisesRegex(ValueError, "exact source substring"):
            export_manifest(private, transcripts)

    def test_unknown_null_fields_round_trip_without_invented_evidence(self):
        private, transcripts = fixture()
        private["claims"][0]["ticker"] = {"value": None, "evidence": []}
        public = export_manifest(private, transcripts)
        with tempfile.TemporaryDirectory() as directory:
            _, claims = load_manifest(save(Path(directory) / "claims.json", public), transcripts)
        self.assertIsNone(claims[0].ticker.value)
        self.assertEqual(claims[0].ticker.evidence, ())

    def test_duplicate_json_and_unpinned_claim_sources_are_rejected(self):
        private, transcripts = fixture()
        public = export_manifest(private, transcripts)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "claims.json"
            path.write_text('{"schema_version":1,"schema_version":2}')
            with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
                load_manifest(path, transcripts)
            public["claims"][0]["source_id"] = "different"
            save(path, public)
            with self.assertRaisesRegex(ValueError, "no pinned source"):
                load_manifest(path, transcripts)

    def test_user_checker_validates_public_input_without_a_model_request(self):
        private, transcripts = fixture()
        public = export_manifest(private, transcripts)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claims_path = save(root / "claims.json", public)
            transcript_dir = root / "transcripts"
            transcript_dir.mkdir()
            for source_id, transcript in transcripts.items():
                save(transcript_dir / f"{source_id}.json", jsonable(transcript))
            selection, claims, restored = load_review_inputs(claims_path, transcript_dir)
            self.assertEqual(selection, private["selection_basis"])
            self.assertEqual(claims[0].to_dict(), private["claims"][0])
            self.assertEqual(restored, transcripts)
            completed = subprocess.run([sys.executable, "scripts/check_semantic_claims.py", "--claims",
                                        str(claims_path), "--transcripts", str(transcript_dir)], cwd=ROOT,
                                       capture_output=True, text=True, check=False)
            self.assertEqual(completed.returncode, 0, completed.stderr)
            output = json.loads(completed.stdout)
            self.assertEqual(output["status"], "validated")
            self.assertEqual(output["claims"], 1)
            self.assertEqual(output["model_requests"], 0)
            self.assertNotIn("Ethereum", completed.stdout)
            public["claims"][0]["ticker"]["evidence"][0]["quote_sha256"] = "0" * 64
            save(claims_path, public)
            failed = subprocess.run(completed.args, cwd=ROOT, capture_output=True, text=True, check=False)
            self.assertEqual(failed.returncode, 1)
            self.assertEqual(json.loads(failed.stdout)["error_code"], "invalid_claim_input")
            self.assertNotIn("Ethereum", failed.stdout)

    def test_source_path_escape_is_rejected_before_opening_a_transcript(self):
        private, transcripts = fixture()
        public = export_manifest(private, transcripts)
        public["claims"][0]["source_id"] = "../outside"
        with tempfile.TemporaryDirectory() as directory:
            path = save(Path(directory) / "claims.json", public)
            with self.assertRaisesRegex(ValueError, "directly inside"):
                load_review_inputs(path, directory)


if __name__ == "__main__":
    unittest.main()
