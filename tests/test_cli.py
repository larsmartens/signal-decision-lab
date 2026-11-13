"""End-to-end public commands; no remote providers or investment assertions."""
from contextlib import redirect_stdout
from dataclasses import replace
from io import StringIO
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from signal_lab.cli import main
from signal_lab.extract import extract_rules
from signal_lab.ingest import load_transcript, write_json
from signal_lab.models import jsonable
from signal_lab.report import render_report


ROOT = Path(__file__).resolve().parents[1]


class CommandTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)

    def run_cli(self, *args):
        stream = StringIO()
        with redirect_stdout(stream):
            code = main(list(args))
        return code, stream.getvalue()

    def test_module_demo_runs_the_pipeline_and_writes_honest_report(self):
        completed = subprocess.run([sys.executable, "-m", "signal_lab", "demo", "--out", str(self.output), "--format", "json"], cwd=ROOT, capture_output=True, text=True, timeout=15)
        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        summary = json.loads(completed.stdout)
        self.assertEqual(summary["entries"], 1)
        self.assertEqual(summary["completed_trades"], 1)
        self.assertEqual(summary["model_calls"], 0)
        bundle = json.loads((self.output / "run.json").read_text())
        self.assertEqual(bundle["transcript"]["kind"], "synthetic")
        self.assertEqual(bundle["replay"]["trades"][0]["entry_time"], "2026-01-01T01:00:00Z")
        html = (self.output / "report.html").read_text()
        self.assertIn("SYNTHETIC SCENARIO", html)
        self.assertIn("No missing fields", html)
        self.assertNotIn("__CHART_DATA__", html)
        self.assertEqual(len(json.loads((self.output / "manifest.json").read_text())["sha256_canonical_payload"]), 64)

    def test_extraction_is_unreviewed_and_stale_today(self):
        output = self.output / "signals.json"
        code, stdout = self.run_cli("extract", str(ROOT / "examples/synthetic-transcript.json"), "--out", str(output), "--format", "json")
        self.assertEqual(code, 0, stdout)
        bundle = json.loads(output.read_text())
        self.assertEqual(bundle["extraction_time_basis"], "actual_processing_time")
        self.assertTrue(all(not s["reviewed"] for s in bundle["signals"]))
        self.assertTrue(all(s["available_at"] > "2026-01-01" for s in bundle["signals"]))

    def test_explicit_historical_review_replay_roundtrip(self):
        original, reviewed, replay = [self.output / name for name in ("extracted.json", "reviewed.json", "replay.json")]
        code, stdout = self.run_cli("extract", str(ROOT / "examples/synthetic-transcript.json"), "--as-of", "2026-01-01T00:05:00Z", "--out", str(original))
        self.assertEqual(code, 0, stdout)
        signal_id = json.loads(original.read_text())["signals"][0]["id"]
        code, stdout = self.run_cli("review", "--input", str(original), "--signal", signal_id, "--reviewer", "synthetic-test-reviewer", "--reviewed-at", "2026-01-01T00:10:00Z", "--out", str(reviewed))
        self.assertEqual(code, 0, stdout)
        code, stdout = self.run_cli("replay", "--signals", str(reviewed), "--bars", str(ROOT / "examples/synthetic-bars.csv"), "--out", str(replay), "--report", str(self.output / "custom.html"), "--format", "json")
        self.assertEqual(code, 0, stdout)
        self.assertEqual(json.loads(stdout)["entries"], 1)
        self.assertEqual(len(json.loads(replay.read_text())["input_hashes"]["bars"]), 64)

    def test_forged_source_roles_fail_at_replay_boundary(self):
        source = load_transcript(ROOT / "examples/synthetic-transcript.json")
        signal = replace(extract_rules(source)[0], stop=108000, reviewed=True)
        path = self.output / "forged.json"
        write_json(path, {"schema_version": 1, "transcript": source, "signals": [signal]})
        code, stdout = self.run_cli("replay", "--signals", str(path), "--bars", str(ROOT / "examples/synthetic-bars.csv"), "--out", str(self.output / "bad.json"))
        self.assertEqual(code, 1)
        self.assertIn("Ungrounded", stdout)
        self.assertFalse((self.output / "bad.json").exists())

    def test_unknown_flags_are_usage_errors_and_create_no_outputs(self):
        code, stdout = self.run_cli("demo", "--judeg", "jeff")
        self.assertEqual(code, 2)
        self.assertIn("unrecognized", stdout)
        self.assertIn("--help", stdout)

    def test_no_args_has_actionable_content(self):
        code, stdout = self.run_cli()
        self.assertEqual(code, 0)
        self.assertIn("paper_only", stdout)
        self.assertIn("python -m signal_lab demo", stdout)

    def test_report_escapes_untrusted_source_text(self):
        source = load_transcript(ROOT / "examples/synthetic-transcript.json")
        bundle = {"transcript": jsonable(source), "signals": jsonable(extract_rules(source))}
        bundle["signals"][0]["evidence"][0]["quote"] = '<script>window.PWNED=1</script>'
        output = self.output / "report.html"
        render_report(bundle, output)
        page = output.read_text()
        self.assertIn("&lt;script&gt;window.PWNED=1&lt;/script&gt;", page)
        self.assertNotIn("<script>window.PWNED=1</script>", page)

    def test_thousands_decimal_and_sentence_punctuation_survive_extraction(self):
        source = load_transcript(ROOT / "examples/synthetic-transcript.json")
        signal = extract_rules(source)[0]
        self.assertEqual((signal.level, signal.stop, signal.target), (100000, 97000, 108000))

    def test_report_rejects_executable_markup_in_numeric_statistics(self):
        bundle = {"signals": [], "replay": {"summary": {"entries": '<img src=x onerror=alert(1)>'}}}
        output = self.output / "malicious.html"
        with self.assertRaises(ValueError):
            render_report(bundle, output)
        self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
