"""Real localhost HTTP contract tests; these do not load Jeff model weights."""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import threading
import unittest

from signal_lab.jeff import ADAPTER_VERSION, FUNCTION, JeffClient
from signal_lab.models import Bar, Evidence, Signal


NOW = datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)


def signal() -> Signal:
    return Signal(
        id="s1", source_id="source1", asset="TEST", side="long",
        statement_type="conditional", trigger="close_above", level=100,
        stop=95, target=110, timeframe_minutes=5, horizon_minutes=60,
        available_at=NOW - timedelta(minutes=10), expires_at=NOW + timedelta(hours=1),
        evidence=(Evidence("seg1", "Buy if the five-minute candle closes above 100."),),
        reviewed=True,
    )


def bar() -> Bar:
    return Bar("TEST", NOW - timedelta(minutes=5), NOW, 99, 102, 98, 101, 500)


def decision(**changes) -> dict:
    result = {
        "value": "buy", "confidence": 0.99,
        "abstained": False, "calibrated": True,
        "probabilities": {"buy": 0.99, "sell": 0.005, "hold": 0.005},
        "interface": "classify", "function": FUNCTION, "version": ADAPTER_VERSION,
        "score": None, "route": [], "decided_by": FUNCTION,
        "escalations": [], "timing": {}, "evidence_refs": [],
    }
    result.update(changes)
    return {"decisions": [result]}


@contextmanager
def endpoint(body=None, status=200, raw=None, headers=None):
    requests = []
    payload = json.dumps(body if body is not None else decision()).encode() if raw is None else raw

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received = self.rfile.read(int(self.headers["Content-Length"]))
            requests.append({"path": self.path, "headers": dict(self.headers), "body": json.loads(received)})
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class JeffClientTests(unittest.TestCase):
    def assert_closed(self, result, code=None):
        self.assertEqual(result["value"], "hold")
        self.assertTrue(result["abstained"])
        self.assertFalse(result["calibrated"])
        self.assertEqual(result["confidence"], 0)
        self.assertEqual(result["probability_source"], "fail_closed_policy")
        self.assertAlmostEqual(sum(result["probabilities"].values()), 1)
        if code:
            self.assertEqual(result["error_code"], code)

    def test_real_http_request_uses_current_contract_and_known_snapshot(self):
        with endpoint() as (url, requests):
            result = JeffClient(url, api_key="test-only-key").judge(signal(), bar())
        self.assertEqual(result["value"], "buy")
        self.assertEqual(result["confidence"], 0.99)
        self.assertFalse(result["abstained"])
        request = requests[0]
        self.assertEqual(request["path"], "/v1/decide")
        self.assertEqual(request["headers"]["Authorization"], "Bearer test-only-key")
        call = request["body"]["calls"][0]
        self.assertEqual(call["function"], FUNCTION)
        self.assertEqual(set(call["context"]), {"desk", "market_context"})
        snapshot = json.loads(call["input"])
        self.assertEqual(snapshot["decision_time"], "2026-11-13T10:00:00Z")
        self.assertEqual(snapshot["completed_bar"]["close"], 101)
        self.assertEqual(snapshot["signal"]["evidence"][0]["segment_id"], "seg1")
        self.assertNotIn("profit_probability", result)
        self.assertNotIn("next_bar", snapshot)

    def test_temporal_and_asset_guards_do_not_send_a_request(self):
        cases = [
            (replace(signal(), available_at=NOW + timedelta(seconds=1)), "future_signal"),
            (replace(signal(), expires_at=NOW), "expired_signal"),
            (replace(signal(), asset="OTHER"), "asset_mismatch"),
        ]
        with endpoint() as (url, requests):
            for value, code in cases:
                with self.subTest(code=code):
                    self.assert_closed(JeffClient(url).judge(value, bar()), code)
            self.assertEqual(requests, [])

    def test_signal_available_exactly_at_close_is_allowed(self):
        with endpoint() as (url, _):
            result = JeffClient(url).judge(replace(signal(), available_at=NOW), bar())
        self.assertEqual(result["value"], "buy")

    def test_reversed_direction_is_vetoed_and_original_decision_is_preserved(self):
        body = decision(value="sell", probabilities={"buy": 0.005, "sell": 0.99, "hold": 0.005})
        with endpoint(body) as (url, _):
            result = JeffClient(url).judge(signal(), bar())
        self.assert_closed(result, "opposite_direction")
        self.assertEqual(result["model_decision"]["value"], "sell")

    def test_valid_short_and_hold_are_supported(self):
        for side, chosen in (("short", "sell"), ("long", "hold"), ("none", "hold")):
            probabilities = {key: 0.005 for key in ("buy", "sell", "hold")}
            probabilities[chosen] = 0.99
            with self.subTest(side=side, chosen=chosen), endpoint(decision(value=chosen, probabilities=probabilities)) as (url, _):
                result = JeffClient(url).judge(replace(signal(), side=side), bar())
                self.assertEqual(result["value"], chosen)
                self.assertFalse(result["abstained"])

    def test_model_abstention_and_missing_calibration_veto_entries(self):
        for changes, code in (({"abstained": True}, "model_abstained"), ({"calibrated": False}, "uncalibrated")):
            with self.subTest(code=code), endpoint(decision(**changes)) as (url, _):
                self.assert_closed(JeffClient(url).judge(signal(), bar()), code)

    def test_malformed_probabilities_and_metadata_fail_closed(self):
        cases = [
            decision(probabilities={"buy": 0.9, "hold": 0.1}),
            decision(probabilities={"buy": 0.9, "sell": 0.1, "hold": 0.1}),
            decision(probabilities={"buy": float("nan"), "sell": 0, "hold": 0}),
            decision(probabilities={"buy": 1.1, "sell": -0.1, "hold": 0}),
            decision(probabilities={"buy": True, "sell": 0, "hold": 0}),
            decision(confidence=True),
            decision(confidence=0.8),
            decision(abstained="false"),
            decision(calibrated=1),
            decision(value="unexpected"),
            decision(function="another.function"),
            decision(version="1.3.0"),
            decision(value="hold", confidence=0.005),
            {"decisions": []},
            {"decisions": [decision()["decisions"][0], decision()["decisions"][0]]},
        ]
        for case in cases:
            with self.subTest(case=case), endpoint(case) as (url, _):
                self.assert_closed(JeffClient(url).judge(signal(), bar()), "malformed_response")

    def test_non_json_duplicate_keys_and_oversized_response_fail_closed(self):
        for raw in (b"not json", b'{"decisions": [], "decisions": []}', b"x" * 1_048_577):
            with self.subTest(size=len(raw)), endpoint(raw=raw) as (url, _):
                self.assert_closed(JeffClient(url).judge(signal(), bar()), "malformed_response")

    def test_http_error_does_not_reflect_response_body_or_secret(self):
        with endpoint(status=503, raw=b"internal details should not leak") as (url, _):
            result = JeffClient(url, api_key="test-secret").judge(signal(), bar())
        self.assert_closed(result, "http_error")
        self.assertIn("503", result["error"])
        self.assertNotIn("test-secret", json.dumps(result))
        self.assertNotIn("internal details", json.dumps(result))

    def test_redirect_is_rejected_without_forwarding_credentials(self):
        with endpoint() as (target_url, target_requests):
            with endpoint(status=307, headers={"Location": target_url}) as (url, _):
                result = JeffClient(url, api_key="test-secret").judge(signal(), bar())
            self.assert_closed(result, "http_error")
            self.assertEqual(target_requests, [])

    def test_unavailable_service_fails_closed(self):
        with endpoint() as (url, _):
            pass
        self.assert_closed(JeffClient(url, timeout=0.2).judge(signal(), bar()), "unavailable")

    def test_invalid_client_configuration_is_rejected(self):
        for url in ("file:///tmp/model", "http://user:secret@localhost:8765", "http://localhost/?token=secret"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                JeffClient(url)
        for timeout in (0, -1, float("inf"), True):
            with self.subTest(timeout=timeout), self.assertRaises(ValueError):
                JeffClient(timeout=timeout)


if __name__ == "__main__":
    unittest.main()
