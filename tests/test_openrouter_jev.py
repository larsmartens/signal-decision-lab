"""Exercise the OpenRouter boundary over HTTP without live model requests."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import socket
import threading
import time
import unittest
from unittest.mock import patch

from signal_lab.openrouter_jev import ENDPOINT, OpenRouterJevClient


KEY = "local-openrouter-test-key"
QUESTIONS = {
    "subject": {
        "type": "choice",
        "instructions": "What does the price expectation concern?",
        "criteria": {"bitcoin": "Bitcoin's price", "other": "Another asset or an indicator"},
    },
    "condition": {
        "type": "choice",
        "instructions": "Does this claim require a future event?",
        "criteria": {"conditional": "An unfulfilled condition is required", "current": "No future condition is required"},
    },
}
STATE = {"passage": "If Bitcoin recovers 82,000, the long case returns; below 79,000 it is invalidated.",
         "context": "The speaker is discussing a potential Bitcoin recovery, not a current entry."}


def response() -> dict:
    return {
        "model": "typesafe/jev-1.14-20261014",
        "provider": "TypeSafe",
        "id": "gen-dec-local-001",
        "answers": {
            "subject": {"type": "choice", "choice": "bitcoin", "confidence": 0.8,
                        "probabilities": {"bitcoin": 0.9, "other": 0.1}},
            "condition": {"type": "choice", "choice": "conditional", "confidence": 0.9,
                          "probabilities": {"conditional": 0.95, "current": 0.05}},
        },
        "usage": {"input_tokens": 500, "output_tokens": 40, "cost": 0.000021},
    }


@contextmanager
def endpoint(body=None, *, raw=None, status=200, headers=None, delay=0):
    requests = []
    payload = json.dumps(response() if body is None else body).encode() if raw is None else raw

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            requests.append({"method": self.command, "path": self.path, "headers": dict(self.headers),
                             "body": json.loads(received) if received else None, "bytes": len(received)})
            if delay:
                time.sleep(delay)
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            for key, value in (headers or {}).items():
                self.send_header(key, value)
            self.end_headers()
            try:
                self.wfile.write(payload)
            except (BrokenPipeError, ConnectionResetError):
                pass

        do_GET = do_POST

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=0.01), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/alpha/decisions", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class OpenRouterJevTests(unittest.TestCase):
    def assert_failure(self, result, code, *, sent):
        self.assertFalse(result["ok"])
        self.assertEqual(result["error_code"], code)
        self.assertEqual(result["answers"], {})
        self.assertIsNone(result["model"])
        self.assertIsNone(result["usage"])
        self.assertEqual(result["request_sent"], sent)
        self.assertEqual(result["cost_known"], not sent)
        self.assertNotIn(KEY, json.dumps(result))
        self.assertNotIn("profit_probability", result)

    def test_semantic_questions_and_evidence_reach_the_decisions_endpoint(self):
        with endpoint() as (url, received):
            result = OpenRouterJevClient(KEY, endpoint=url).decide(STATE, QUESTIONS)
        self.assertTrue(result["ok"])
        self.assertEqual(len(received), 1)
        request = received[0]
        self.assertEqual((request["method"], request["path"]), ("POST", "/api/alpha/decisions"))
        self.assertEqual(request["headers"]["Authorization"], f"Bearer {KEY}")
        self.assertEqual(request["headers"]["Content-Type"], "application/json")
        self.assertEqual(request["body"], {"model": "typesafe/jev-1.14", "state": STATE, "questions": QUESTIONS})
        self.assertEqual(result["answers"], response()["answers"])
        self.assertEqual(result["request_model"], "typesafe/jev-1.14")
        self.assertEqual(result["model"], "typesafe/jev-1.14-20261014")
        self.assertEqual(result["provider"], "TypeSafe")
        self.assertEqual(result["request_id"], "gen-dec-local-001")
        self.assertEqual(result["usage"], {"input_tokens": 500, "output_tokens": 40, "cost": 0.000021})
        self.assertTrue(result["cost_known"])
        self.assertGreaterEqual(result["latency_ms"], 0)
        self.assertNotIn(KEY, json.dumps(result))

    def test_choice_probability_and_provider_confidence_remain_distinct(self):
        with endpoint() as (url, _):
            result = OpenRouterJevClient(KEY, endpoint=url).decide(STATE, QUESTIONS)
        self.assertEqual(result["answers"]["subject"]["confidence"], 0.8)
        self.assertEqual(result["answers"]["subject"]["probabilities"]["bitcoin"], 0.9)

    def test_environment_key_is_used_without_becoming_part_of_the_request_body(self):
        with endpoint() as (url, received), patch.dict(os.environ, {"OPENROUTER_API_KEY": KEY}, clear=True):
            client = OpenRouterJevClient(endpoint=url)
            self.assertTrue(client.configured)
            self.assertTrue(client.decide(STATE, QUESTIONS)["ok"])
        self.assertEqual(received[0]["headers"]["Authorization"], f"Bearer {KEY}")
        self.assertNotIn(KEY, json.dumps(received[0]["body"]))
        self.assertNotIn(KEY, repr(client))

    def test_explicit_key_takes_precedence_over_environment(self):
        with endpoint() as (url, received), patch.dict(os.environ, {"OPENROUTER_API_KEY": "other-key"}, clear=True):
            result = OpenRouterJevClient(KEY, endpoint=url).decide(STATE, QUESTIONS)
        self.assertTrue(result["ok"])
        self.assertEqual(received[0]["headers"]["Authorization"], f"Bearer {KEY}")

    def test_missing_key_returns_no_answers_without_sending_source_text(self):
        with endpoint() as (url, received), patch.dict(os.environ, {}, clear=True):
            client = OpenRouterJevClient(endpoint=url)
            self.assertFalse(client.configured)
            self.assert_failure(client.decide(STATE, QUESTIONS), "missing_api_key", sent=False)
        self.assertEqual(received, [])

    def test_preflight_needs_no_key_and_identifies_production_transport(self):
        with patch.dict(os.environ, {}, clear=True):
            client = OpenRouterJevClient()
            plan = client.preflight(STATE, QUESTIONS)
        self.assertFalse(client.configured)
        self.assertEqual(plan["endpoint"], ENDPOINT)
        self.assertEqual(plan["transport"], "openrouter")
        self.assertEqual(plan["request_model"], "typesafe/jev-1.14")
        self.assertEqual(plan["expected_model"], "typesafe/jev-1.14-20261014")
        self.assertGreater(plan["request_bytes"], len(json.dumps(STATE).encode()))
        self.assertNotIn("state", plan)
        self.assertNotIn("questions", plan)

    def test_preflight_identifies_loopback_without_a_request_and_counts_sent_bytes(self):
        state = {"passage": "The price is quoted in €; the scenario is conditional."}
        with endpoint() as (url, received), patch.dict(os.environ, {}, clear=True):
            unconfigured = OpenRouterJevClient(endpoint=url)
            plan = unconfigured.preflight(state, QUESTIONS)
            self.assertFalse(unconfigured.configured)
            self.assertEqual(received, [])
            self.assertEqual(plan["endpoint"], url)
            self.assertEqual(plan["transport"], "loopback_test")
            client = OpenRouterJevClient(KEY, endpoint=url)
            self.assertEqual(client.preflight(state, QUESTIONS), plan)
            result = client.decide(state, QUESTIONS)
        self.assertTrue(result["ok"])
        self.assertEqual(len(received), 1)
        self.assertEqual(plan["request_bytes"], received[0]["bytes"])
        self.assertNotIn(KEY, json.dumps(plan))

    def test_preflight_rejects_invalid_or_oversized_full_requests_before_network(self):
        large_questions = deepcopy(QUESTIONS)
        large_questions["subject"]["instructions"] = "x" * 1024
        cases = [(None, QUESTIONS), (STATE, {}), ({"price": float("nan")}, QUESTIONS),
                 ("\ud800", QUESTIONS), ("€" * 300, QUESTIONS), ("", large_questions)]
        with endpoint() as (url, received), patch.dict(os.environ, {}, clear=True):
            client = OpenRouterJevClient(endpoint=url, max_input_bytes=1024)
            client.preflight("x" * 300, QUESTIONS)
            for number, (state, questions) in enumerate(cases):
                with self.subTest(number=number), self.assertRaises(ValueError):
                    client.preflight(state, questions)
        self.assertEqual(received, [])

    def test_invalid_requests_never_leave_the_process(self):
        circular = []
        circular.append(circular)
        cases = [
            (None, QUESTIONS), (12, QUESTIONS), ({"price": float("nan")}, QUESTIONS),
            ({1: "ambiguous key"}, QUESTIONS), ({"nested": [{1: "bad"}]}, QUESTIONS),
            (circular, QUESTIONS), ({"invalid": {1, 2}}, QUESTIONS), ("\ud800", QUESTIONS),
            (STATE, {}), (STATE, []), (STATE, {"": QUESTIONS["subject"]}),
            (STATE, {"subject": {"type": "noul", "instructions": "Is this Bitcoin?"}}),
            (STATE, {"subject": {"type": "choice", "instructions": " ", "criteria": {"yes": "Yes"}}}),
            (STATE, {"subject": {"type": "choice", "instructions": "Select", "criteria": {}}}),
            (STATE, {"subject": {"type": "choice", "instructions": "Select", "criteria": {"yes": ""}}}),
            (STATE, {"subject": {"type": "choice", "instructions": "Select", "criteria": {1: "Yes"}}}),
            (STATE, {"subject": {"type": "choice", "instructions": "Select",
                                  "criteria": {str(i): "A choice" for i in range(256)}}}),
        ]
        with endpoint() as (url, received):
            client = OpenRouterJevClient(KEY, endpoint=url)
            for number, (state, questions) in enumerate(cases):
                with self.subTest(number=number):
                    self.assert_failure(client.decide(state, questions), "invalid_request", sent=False)
        self.assertEqual(received, [])

    def test_request_size_counts_utf8_bytes_and_questions(self):
        with endpoint() as (url, received):
            client = OpenRouterJevClient(KEY, endpoint=url, max_input_bytes=1024)
            self.assertTrue(client.decide("x" * 300, QUESTIONS)["ok"])
            self.assert_failure(client.decide("€" * 300, QUESTIONS), "request_too_large", sent=False)
            large_questions = deepcopy(QUESTIONS)
            large_questions["subject"]["instructions"] = "x" * 1024
            self.assert_failure(client.decide("", large_questions), "request_too_large", sent=False)
        self.assertEqual(len(received), 1)
        self.assertLessEqual(received[0]["bytes"], 1024)

    def test_invalid_model_pin_provider_and_audit_fields_reject_the_response(self):
        changes = [
            {"model": "typesafe/jev-1.13-20260917"}, {"model": "typesafe/jev-1.14"},
            {"provider": "Another Provider"}, {"provider": None}, {"id": None},
            {"id": "bad\nidentifier"}, {"id": "a" * 201}, {"id": f"gen-dec-{KEY}"},
            {"usage": None}, {"usage": {"input_tokens": 500, "output_tokens": 40}},
            {"usage": {"input_tokens": True, "output_tokens": 40, "cost": 0}},
            {"usage": {"input_tokens": 500, "output_tokens": -1, "cost": 0}},
            {"usage": {"input_tokens": 500, "output_tokens": 40, "cost": True}},
            {"usage": {"input_tokens": 500, "output_tokens": 40, "cost": -0.1}},
            {"usage": {"input_tokens": 500, "output_tokens": 40, "cost": float("inf")}},
        ]
        for number, change in enumerate(changes):
            body = response()
            body.update(change)
            with self.subTest(number=number), endpoint(body) as (url, received):
                self.assert_failure(OpenRouterJevClient(KEY, endpoint=url).decide(STATE, QUESTIONS),
                                    "malformed_response", sent=True)
            self.assertEqual(len(received), 1)

    def test_missing_extra_or_invalid_answers_reject_the_whole_response(self):
        changes = [
            {"type": "noul"}, {"choice": "missing"}, {"choice": True}, {"choice": "other"},
            {"probabilities": {"bitcoin": 0.9}}, {"probabilities": {"bitcoin": 0.9, "other": 0.1, "third": 0}},
            {"probabilities": {"bitcoin": 0.9, "other": 0.2}},
            {"probabilities": {"bitcoin": True, "other": 0}},
            {"probabilities": {"bitcoin": 1.1, "other": -0.1}},
            {"probabilities": {"bitcoin": "0.9", "other": 0.1}},
            {"confidence": False}, {"confidence": None}, {"confidence": 1.1},
        ]
        bodies = []
        for change in changes:
            body = response()
            body["answers"]["subject"].update(change)
            bodies.append(body)
        missing = response()
        del missing["answers"]["condition"]
        bodies.append(missing)
        extra = response()
        extra["answers"]["unasked"] = extra["answers"]["condition"]
        bodies.append(extra)
        for number, body in enumerate(bodies):
            with self.subTest(number=number), endpoint(body) as (url, _):
                self.assert_failure(OpenRouterJevClient(KEY, endpoint=url).decide(STATE, QUESTIONS),
                                    "malformed_response", sent=True)

    def test_corrupt_json_and_reflected_error_content_are_not_returned(self):
        good = json.dumps(response())
        bodies = [b"not json", b"\xff", b"[]", b"null", b'{"duplicate":1,"duplicate":2}',
                  good.replace('"bitcoin": 0.9', '"bitcoin": 0.9, "bitcoin": 0.9').encode(),
                  good.replace('"bitcoin": 0.9', '"bitcoin": NaN').encode(),
                  json.dumps({"error": {"message": KEY}}).encode()]
        for number, body in enumerate(bodies):
            with self.subTest(number=number), endpoint(raw=body) as (url, _):
                self.assert_failure(OpenRouterJevClient(KEY, endpoint=url).decide(STATE, QUESTIONS),
                                    "malformed_response", sent=True)

    def test_response_size_limit_returns_unknown_cost_and_no_partial_answer(self):
        with endpoint() as (url, _):
            self.assert_failure(OpenRouterJevClient(KEY, endpoint=url, max_response_bytes=100).decide(STATE, QUESTIONS),
                                "response_too_large", sent=True)

    def test_http_errors_are_not_retried_or_reflected(self):
        for status in (401, 402, 429, 500, 503):
            with self.subTest(status=status), endpoint({"error": KEY}, status=status) as (url, received):
                result = OpenRouterJevClient(KEY, endpoint=url).decide(STATE, QUESTIONS)
                self.assert_failure(result, "http_error", sent=True)
                self.assertEqual(result["http_status"], status)
            self.assertEqual(len(received), 1)

    def test_redirect_never_sends_credential_or_evidence_to_its_destination(self):
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status), endpoint() as (destination, forwarded):
                with endpoint(status=status, headers={"Location": destination}) as (url, received):
                    result = OpenRouterJevClient(KEY, endpoint=url).decide(STATE, QUESTIONS)
                self.assert_failure(result, "http_error", sent=True)
                self.assertEqual(result["http_status"], status)
            self.assertEqual(len(received), 1)
            self.assertEqual(forwarded, [])

    def test_timeout_stops_after_one_attempt_and_does_not_claim_zero_cost(self):
        with endpoint(delay=0.2) as (url, received):
            result = OpenRouterJevClient(KEY, endpoint=url, timeout=0.02).decide(STATE, QUESTIONS)
            self.assert_failure(result, "unavailable", sent=True)
        self.assertEqual(len(received), 1)

    def test_connection_failure_has_no_model_answer(self):
        with socket.socket() as sock:
            sock.bind(("127.0.0.1", 0))
            port = sock.getsockname()[1]
        client = OpenRouterJevClient(KEY, endpoint=f"http://127.0.0.1:{port}/api/alpha/decisions", timeout=0.1)
        self.assert_failure(client.decide(STATE, QUESTIONS), "unavailable", sent=True)

    def test_constructor_rejects_unpinned_models_and_remote_credential_destinations(self):
        cases = [
            {"model": "~typesafe/jev-latest"}, {"model": "jev-1.14.0"},
            {"expected_model": "typesafe/jev-1.13-20260917"}, {"expected_model": "typesafe/jev-1.14"},
            {"endpoint": "https://example.com/api/alpha/decisions"},
            {"endpoint": "http://openrouter.ai/api/alpha/decisions"},
            {"endpoint": ENDPOINT + "?key=secret"}, {"endpoint": ENDPOINT + "#fragment"},
            {"endpoint": "https://user:password@openrouter.ai/api/alpha/decisions"},
            {"endpoint": "http://127.0.0.1:1234/not-decisions"},
            {"endpoint": "http://@127.0.0.1:1234/api/alpha/decisions"},
            {"endpoint": "http://127.0.0.1:bad/api/alpha/decisions"},
            {"endpoint": "https://openrouter.ai.evil.test/api/alpha/decisions"},
            {"timeout": 0}, {"timeout": True}, {"timeout": float("nan")},
            {"max_input_bytes": 0}, {"max_input_bytes": True}, {"max_input_bytes": 262145},
            {"max_response_bytes": 1.5}, {"api_key": ""}, {"api_key": "with space"},
            {"api_key": "with\nnewline"}, {"api_key": "non-ascii-€"},
        ]
        for number, kwargs in enumerate(cases):
            with self.subTest(number=number), self.assertRaises(ValueError):
                OpenRouterJevClient(**kwargs)


if __name__ == "__main__":
    unittest.main()
