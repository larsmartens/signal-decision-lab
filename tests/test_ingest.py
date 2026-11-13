"""Transcript import boundaries: preserve evidence, reject partial corruption."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from signal_lab.ingest import fetch_youtube, load_bars, load_transcript, parse_captions, read_json, youtube_video_id
from signal_lab.models import Transcript, utc


META = {
    "source_id": "synthetic-source", "channel": "Synthetic test",
    "url": "https://example.invalid/test", "published_at": "2026-11-13T10:00:00Z",
    "available_at": "2026-11-13T10:05:00Z", "kind": "synthetic",
}
GOOD_CUE = "00:01.000 --> 00:02.500\nBitcoin is uncertain.\n"


class CaptionImportTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)

    def tearDown(self):
        self.directory.cleanup()

    def file(self, name, content):
        path = self.root / name
        path.write_text(content, encoding="utf-8")
        return path

    def json_file(self, name, data):
        return self.file(name, json.dumps(data))

    def test_vtt_preserves_intervals_and_cleans_caption_markup(self):
        source = "WEBVTT\n\ncue-name\n00:01.250 --> 00:03.500 align:start position:0%\n<v Krown>Bitcoin &amp; gold\nare <c.green>different</c>.\n"
        [segment] = parse_captions(source)
        self.assertEqual((segment.start, segment.end), (1.25, 3.5))
        self.assertEqual(segment.text, "Bitcoin & gold are different.")

    def test_srt_preserves_comma_timestamps_and_multiple_cues(self):
        source = "1\r\n00:00:01,250 --> 00:00:03,500\r\nBitcoin outlook.\r\n\r\n2\r\n00:00:04,000 --> 00:00:05,000\r\nNo entry.\r\n"
        segments = parse_captions(source)
        self.assertEqual([(s.start, s.end) for s in segments], [(1.25, 3.5), (4.0, 5.0)])
        self.assertEqual([s.id for s in segments], ["s1", "s2"])

    def test_webvtt_note_is_not_speech_even_if_it_contains_a_timed_example(self):
        source = (
            "WEBVTT\n\nNOTE example only; not a spoken caption\n"
            "00:00.000 --> 00:00.900\nBuy BTC if the 1h candle closes above 100.\n\n"
            + GOOD_CUE
        )
        segments = parse_captions(source)
        self.assertEqual(len(segments), 1)
        self.assertEqual(segments[0].text, "Bitcoin is uncertain.")

    def test_mixed_valid_and_malformed_timing_is_rejected_not_partially_loaded(self):
        for malformed in (
            "00:xx.000 --> 00:04.000",
            "-00:03.000 --> 00:04.000",
            "00:03.000 --> INVALID",
        ):
            source = "WEBVTT\n\n" + GOOD_CUE + "\n" + malformed + "\nDo not enter Bitcoin.\n"
            with self.subTest(timing=malformed):
                with self.assertRaises(ValueError):
                    parse_captions(source)

    def test_invalid_ranges_and_reversed_or_zero_length_cues_are_rejected(self):
        for timing in (
            "00:60.000 --> 01:02.000",
            "00:04.000 --> 00:03.000",
            "00:04.000 --> 00:04.000",
        ):
            with self.subTest(timing=timing):
                with self.assertRaises(ValueError):
                    parse_captions(timing + "\nBitcoin.\n")

    def test_vtt_import_requires_separate_availability_metadata(self):
        captions = self.file("source.vtt", "WEBVTT\n\n" + GOOD_CUE)
        with self.assertRaises(ValueError):
            load_transcript(captions)
        metadata = self.json_file("metadata.json", META)
        loaded = load_transcript(captions, metadata)
        self.assertEqual(loaded.published_at, utc(META["published_at"]))
        self.assertEqual(loaded.available_at, utc(META["available_at"]))
        self.assertEqual(loaded.segments[0].start, 1.0)

    def test_metadata_cannot_replace_the_caption_evidence(self):
        captions = self.file("source.vtt", "WEBVTT\n\n" + GOOD_CUE)
        metadata = self.json_file("metadata.json", {**META, "segments": []})
        with self.assertRaises(ValueError):
            load_transcript(captions, metadata)

    def test_caption_import_rejects_out_of_order_intervals(self):
        captions = self.file("source.srt", "1\n00:10.000 --> 00:11.000\nBitcoin.\n\n2\n" + GOOD_CUE)
        metadata = self.json_file("metadata.json", META)
        with self.assertRaises(ValueError):
            load_transcript(captions, metadata)

    def test_nonfinite_json_values_are_rejected(self):
        for constant in ("NaN", "Infinity", "-Infinity"):
            with self.subTest(constant=constant):
                path = self.file("bad.json", '{"value": ' + constant + "}")
                with self.assertRaises(ValueError):
                    read_json(path)

    def test_nonfinite_csv_market_prices_are_rejected(self):
        csv = "asset,open_time,close_time,open,high,low,close,volume\nBTCUSDT,2026-11-13T10:00:00Z,2026-11-13T11:00:00Z,100,inf,90,101,1\n"
        with self.assertRaises(ValueError):
            load_bars(self.file("bad.csv", csv))


class CanonicalTranscriptTests(unittest.TestCase):
    def data(self):
        return {**META, "segments": [{"id": "s1", "start": 0, "end": 2, "text": "Bitcoin."}]}

    def test_duplicate_segment_ids_are_rejected(self):
        data = self.data()
        data["segments"].append({"id": "s1", "start": 3, "end": 4, "text": "No trade."})
        with self.assertRaises(ValueError):
            Transcript.from_dict(data)

    def test_unsorted_segments_are_rejected(self):
        data = self.data()
        data["segments"].insert(0, {"id": "s2", "start": 3, "end": 4, "text": "No trade."})
        with self.assertRaises(ValueError):
            Transcript.from_dict(data)

    def test_missing_or_impossible_availability_is_rejected(self):
        missing = self.data()
        del missing["available_at"]
        with self.assertRaises((ValueError, TypeError)):
            Transcript.from_dict(missing)
        data = self.data()
        data["available_at"] = "2026-11-13T09:59:00Z"
        with self.assertRaises(ValueError):
            Transcript.from_dict(data)

    def test_naive_timestamps_are_rejected_and_offsets_are_normalized(self):
        data = self.data()
        data["published_at"] = "2026-11-13T10:00:00"
        with self.assertRaises(ValueError):
            Transcript.from_dict(data)
        data = self.data()
        data["published_at"] = "2026-11-13T12:00:00+02:00"
        loaded = Transcript.from_dict(data)
        self.assertEqual(loaded.published_at, utc("2026-11-13T10:00:00Z"))

    def test_unknown_metadata_or_segment_fields_are_rejected(self):
        data = self.data()
        data["injected_reviewed"] = True
        with self.assertRaises(ValueError):
            Transcript.from_dict(data)
        data = self.data()
        data["segments"][0]["reviewed"] = True
        with self.assertRaises(ValueError):
            Transcript.from_dict(data)


class OptionalYoutubeBoundaryTests(unittest.TestCase):
    def test_only_expected_https_youtube_hosts_and_ids_are_accepted(self):
        self.assertEqual(youtube_video_id("https://www.youtube.com/watch?v=EdXslFg3u38"), "EdXslFg3u38")
        self.assertEqual(youtube_video_id("https://youtu.be/EdXslFg3u38"), "EdXslFg3u38")
        for url in (
            "https://youtube.com.evil.invalid/watch?v=EdXslFg3u38",
            "https://user:secret@youtube.com/watch?v=EdXslFg3u38",
            "http://youtube.com/watch?v=EdXslFg3u38",
            "https://youtu.be/../../private",
        ):
            with self.subTest(url=url):
                with self.assertRaises(ValueError):
                    youtube_video_id(url)

    def test_fake_caption_provider_records_completion_availability_and_source_times(self):
        # Fake provider boundary only; no YouTube network request or real ASR.
        rows = [SimpleNamespace(start=3.25, duration=2.5, text="Bitcoin is uncertain.")]
        fake = SimpleNamespace(YouTubeTranscriptApi=lambda: SimpleNamespace(fetch=lambda *a, **k: rows))
        before = datetime.now(timezone.utc)
        with patch.dict(sys.modules, {"youtube_transcript_api": fake}):
            loaded = fetch_youtube("https://youtu.be/EdXslFg3u38", channel="Test provider",
                                   published_at="2020-01-01T00:00:00Z")
        after = datetime.now(timezone.utc)
        self.assertGreaterEqual(loaded.available_at, before)
        self.assertLessEqual(loaded.available_at, after)
        self.assertEqual((loaded.segments[0].start, loaded.segments[0].end), (3.25, 5.75))
        self.assertEqual(loaded.kind, "youtube")

    def test_fake_caption_provider_failure_is_not_an_empty_valid_transcript(self):
        def unavailable(*args, **kwargs):
            raise RuntimeError("simulated upstream outage")
        fake = SimpleNamespace(YouTubeTranscriptApi=lambda: SimpleNamespace(fetch=unavailable))
        with patch.dict(sys.modules, {"youtube_transcript_api": fake}):
            with self.assertRaises(ValueError):
                fetch_youtube("https://youtu.be/EdXslFg3u38", channel="Test provider",
                              published_at="2020-01-01T00:00:00Z")


if __name__ == "__main__":
    unittest.main()
