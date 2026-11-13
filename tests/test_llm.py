"""HTTP contract/adversarial tests using a local stub, not a real language model."""
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest

from signal_lab.llm import LLMExtractor
from signal_lab.models import Segment, Transcript


T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
TEXT = "BTC: go long if the 1 hour close above 100. Stop 90. Target 140. Valid for 24 hours."


def transcript(text=TEXT, segments=None):
    return Transcript("test-source", "Synthetic test", "https://example.test/video", T0,
                      T0 + timedelta(minutes=5),
                      tuple(segments or [Segment("s1", 0, 20, text)]), "synthetic")


def candidate(**changes):
    return {"asset": "BTCUSDT", "side": "long", "statement_type": "conditional",
            "trigger": "close_above", "level": 100, "stop": 90, "target": 140,
            "timeframe_minutes": 60, "horizon_minutes": 1440,
            "evidence": [{"segment_id": "s1", "quote": TEXT}], **changes}


def envelope(content):
    return json.dumps({"choices": [{"message": {"content": content}}]}).encode()


def response(candidates=None, *, content=None):
    body = content if content is not None else json.dumps({"candidates": candidates or []})
    return 200, {}, envelope(body)


@contextmanager
def http_stub(responses):
    """Record real local HTTP requests and serve caller-specified wire responses."""
    received = []
    pending = list(responses)

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            received.append({"path": self.path, "body": body, "headers": dict(self.headers)})
            status, headers, raw = pending.pop(0) if pending else (500, {}, b"unexpected request")
            self.send_response(status)
            for key, value in headers.items():
                self.send_header(key, value.format(port=self.server.server_port))
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            try:
                self.wfile.write(raw)
            except (BrokenPipeError, ConnectionResetError):
                pass

        def do_GET(self):
            received.append({"path": self.path, "body": b"", "headers": dict(self.headers)})
            self.send_response(500)
            self.end_headers()

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    worker = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
    worker.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/v1", received
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=2)


class LLMExtractionContractTests(unittest.TestCase):
    def extract_wire(self, candidates, source=None, **kwargs):
        with http_stub([response(candidates)]) as (url, received):
            result = LLMExtractor(url, "local-test-model").extract(
                source or transcript(), extracted_at=T0 + timedelta(minutes=10), **kwargs)
        return result, received

    def test_conditional_signal_preserves_roles_quotes_and_requires_review(self):
        signals, received = self.extract_wire([candidate()])
        self.assertEqual(len(signals), 1)
        signal = signals[0]
        self.assertEqual((signal.statement_type, signal.side, signal.trigger),
                         ("conditional", "long", "close_above"))
        self.assertEqual((signal.level, signal.stop, signal.target), (100, 90, 140))
        self.assertFalse(signal.reviewed)
        self.assertEqual(signal.issues, ())
        self.assertEqual(signal.evidence[0].quote, TEXT)
        self.assertEqual(signal.available_at, T0 + timedelta(minutes=10))
        self.assertEqual(received[0]["path"], "/v1/chat/completions")
        request = json.loads(received[0]["body"])
        self.assertEqual([m["role"] for m in request["messages"]], ["system", "user"])
        self.assertIn("UNTRUSTED", request["messages"][0]["content"])

    def test_empty_candidates_is_success_without_invented_signal(self):
        signals, _ = self.extract_wire([])
        self.assertEqual(signals, [])

    def test_invalid_json_and_malformed_envelopes_are_rejected(self):
        responses = [(200, {}, b"not JSON"), (200, {}, b"{}"),
                     (200, {}, b'{"choices": []}'), response(content="{"),
                     response(content='[{"candidates": []}]'),
                     response(content='{"candidates": [], "reviewed": true}')]
        for wire in responses:
            with self.subTest(wire=wire), http_stub([wire]) as (url, _):
                with self.assertRaises(ValueError):
                    LLMExtractor(url, "test").extract(transcript(), extracted_at=T0)

    def test_model_cannot_set_reviewed_confidence_timestamps_or_unknown_fields(self):
        for extra in ({"reviewed": True}, {"confidence": .99},
                      {"available_at": "2020-01-01T00:00:00Z"}, {"magic": "buy"}):
            with self.subTest(extra=extra), self.assertRaises(ValueError):
                self.extract_wire([candidate(**extra)])
        incomplete = candidate()
        del incomplete["stop"]
        with self.assertRaises(ValueError):
            self.extract_wire([incomplete])

    def test_quote_must_be_exact_and_reference_a_real_segment(self):
        for evidence in ([{"segment_id": "s1", "quote": TEXT.replace("90", "95")}],
                         [{"segment_id": "invented", "quote": TEXT}]):
            with self.subTest(evidence=evidence), self.assertRaises(ValueError):
                self.extract_wire([candidate(evidence=evidence)])

    def test_numbers_cannot_be_reassigned_to_different_roles(self):
        for changes in ({"stop": 140, "target": 90}, {"level": 90},
                        {"trigger": "close_below"}, {"timeframe_minutes": 240},
                        {"horizon_minutes": 60}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.extract_wire([candidate(**changes)])

    def test_quote_cannot_cherry_pick_away_negation(self):
        text = "Do not buy. " + TEXT
        with self.assertRaises(ValueError):
            self.extract_wire([candidate()], transcript(text))

    def test_quote_cannot_cherry_pick_away_retrospective_context(self):
        text = "Yesterday I said: " + TEXT
        with self.assertRaises(ValueError):
            self.extract_wire([candidate()], transcript(text))

    def test_unsupported_condition_remains_a_blocker(self):
        text = TEXT + " Enter only if volume confirms."
        signals, _ = self.extract_wire([candidate(evidence=[{"segment_id": "s1", "quote": text}])],
                                       transcript(text))
        self.assertIn("unsupported_condition", signals[0].issues)
        with self.assertRaises(ValueError):
            self.extract_wire([candidate()], transcript(text))

    def test_missing_stop_is_preserved_as_unknown_with_issue(self):
        text = TEXT.replace(" Stop 90.", "")
        signals, _ = self.extract_wire([candidate(stop=None,
            evidence=[{"segment_id": "s1", "quote": text}])], transcript(text))
        self.assertIsNone(signals[0].stop)
        self.assertIn("missing_stop", signals[0].issues)

    def test_overlap_is_sent_with_timestamps_and_identical_candidates_deduplicate(self):
        segments = [Segment(f"s{i}", (i-1)*20, i*20, TEXT if i == 3 else "General discussion.")
                    for i in range(1, 6)]
        item = candidate(evidence=[{"segment_id": "s3", "quote": TEXT}])
        with http_stub([response([item]), response([item])]) as (url, received):
            signals = LLMExtractor(url, "test").extract(transcript(segments=segments),
                extracted_at=T0 + timedelta(minutes=10), chunk_size=3, overlap=1)
        self.assertEqual(len(signals), 1)
        batches = [json.loads(json.loads(r["body"])["messages"][1]["content"])["segments"]
                   for r in received]
        self.assertEqual([[s["id"] for s in batch] for batch in batches],
                         [["s1", "s2", "s3"], ["s3", "s4", "s5"]])
        self.assertEqual((batches[1][0]["start"], batches[1][0]["end"]), (40, 60))

    def test_later_chunk_outage_does_not_return_partial_or_substitute_signals(self):
        segments = [Segment("s1", 0, 20, TEXT), Segment("s2", 20, 40, "More discussion.")]
        with http_stub([response([candidate()]), (503, {}, b"private provider diagnostics")]) as (url, received):
            with self.assertRaises(ValueError) as error:
                LLMExtractor(url, "test").extract(transcript(segments=segments),
                    extracted_at=T0, chunk_size=1, overlap=0)
        self.assertEqual(len(received), 2)
        self.assertIn("no substitute signals", str(error.exception))
        self.assertNotIn("private provider diagnostics", str(error.exception))

    def test_remote_http_and_credential_bearing_urls_are_rejected_before_network(self):
        urls = ["http://example.com/v1", "http://127.0.0.1.attacker.test/v1",
                "ftp://localhost/v1", "https://user:secret@example.com/v1",
                "https://example.com/v1?api_key=secret", "https://example.com/v1#secret"]
        for url in urls:
            with self.subTest(url=url), self.assertRaises(ValueError) as error:
                LLMExtractor(url, "test")
            self.assertNotIn("secret", str(error.exception))

    def test_redirect_cannot_forward_authorization_or_disclose_token(self):
        secret = "fake-test-key-never-forward"
        redirect = (307, {"Location": "http://127.0.0.1:{port}/leak"}, b"")
        with http_stub([redirect]) as (url, received):
            with self.assertRaises(ValueError) as error:
                LLMExtractor(url, "test", api_key=secret).extract(transcript(), extracted_at=T0)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0]["headers"]["Authorization"], "Bearer " + secret)
        self.assertNotIn(secret, str(error.exception))
        self.assertIn("redirect", str(error.exception).lower())

    def test_delayed_inference_updates_availability_without_renewing_expiry(self):
        late = T0 + timedelta(days=2)
        with http_stub([response([candidate()])]) as (url, _):
            result = LLMExtractor(url, "test").extract(transcript(), extracted_at=late)
        self.assertEqual(result[0].available_at, late)
        self.assertEqual(result[0].expires_at, T0 + timedelta(days=1))
        self.assertLess(result[0].expires_at, result[0].available_at)

    def test_earlier_claimed_inference_cannot_backdate_transcript_availability(self):
        with http_stub([response([candidate()])]) as (url, _):
            result = LLMExtractor(url, "test").extract(transcript(), extracted_at=T0)
        self.assertEqual(result[0].available_at, transcript().available_at)

    def test_default_availability_is_actual_inference_completion(self):
        before = datetime.now(timezone.utc)
        with http_stub([response([candidate()])]) as (url, _):
            result = LLMExtractor(url, "test").extract(transcript())
        self.assertGreaterEqual(result[0].available_at, before)

    def test_nonfinite_boolean_and_negative_numeric_fields_are_rejected(self):
        for changes in ({"level": True}, {"stop": float("nan")}, {"target": float("inf")},
                        {"horizon_minutes": True}, {"timeframe_minutes": -1}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.extract_wire([candidate(**changes)])

    def test_evidence_shape_errors_are_structured_validation_errors(self):
        for malformed in (None, 42, "evidence", [{"segment_id": "s1", "quote": TEXT, "reviewed": True}]):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                self.extract_wire([candidate(evidence=malformed)])

    def test_oversized_wire_response_is_rejected(self):
        with http_stub([(200, {}, b" " * 2_000_001)]) as (url, _):
            with self.assertRaises(ValueError):
                LLMExtractor(url, "test").extract(transcript(), extracted_at=T0)

    def test_too_many_candidates_are_rejected(self):
        with self.assertRaises(ValueError):
            self.extract_wire([candidate()] * 101)

    def test_invalid_chunk_parameters_do_not_contact_provider(self):
        for kwargs in ({"chunk_size": 0}, {"overlap": -1}, {"chunk_size": 2, "overlap": 2},
                       {"chunk_size": True}, {"chunk_size": 101}):
            with self.subTest(kwargs=kwargs), http_stub([]) as (url, received):
                with self.assertRaises(ValueError):
                    LLMExtractor(url, "test").extract(transcript(), **kwargs)
                self.assertEqual(received, [])

    def test_timeout_cannot_be_nan_boolean_or_nonpositive(self):
        for timeout in (float("nan"), True, 0, -1, 301):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                LLMExtractor("http://127.0.0.1:1/v1", "test", timeout=timeout)


if __name__ == "__main__":
    unittest.main()
