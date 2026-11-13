"""Real localhost HTTP tests of the TypeSafe contract, without live Jev inference."""
from __future__ import annotations

from contextlib import contextmanager, redirect_stdout
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import io
import os
from pathlib import Path
import socket
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from signal_lab.engine import Policy
from signal_lab.cli import main
from signal_lab.jev import JevClient, MODEL
from signal_lab.models import Bar, Evidence, Signal
from signal_lab.replay import run_replay


NOW = datetime(2026, 11, 13, 10, 0, tzinfo=timezone.utc)
KEY = "local-test-key"


def signal() -> Signal:
    return Signal(
        id="s1", source_id="source1", asset="BTCUSDT", side="long",
        statement_type="conditional", trigger="close_above", level=100,
        stop=95, target=110, timeframe_minutes=5, horizon_minutes=60,
        available_at=NOW - timedelta(minutes=10), expires_at=NOW + timedelta(hours=1),
        evidence=(Evidence("seg1", "Buy if the five-minute candle closes above 100; stop 95; target 110."),),
        reviewed=True,
    )


def bar() -> Bar:
    return Bar("BTCUSDT", NOW - timedelta(minutes=5), NOW, 99, 102, 98, 101, 500)


def choice(value="buy", *, model=MODEL, **changes) -> dict:
    probabilities = {"buy": 0.1, "sell": 0.1, "hold": 0.1}
    probabilities[value] = 0.8
    answer = {"type": "choice", "choice": value, "confidence": 0.7, "probabilities": probabilities}
    answer.update(changes)
    return {"model": model, "answers": {"direction": answer},
            "usage": {"input_tokens": 350, "output_tokens": 30}}


@contextmanager
def endpoint(body=None, *, status=200, raw=None, headers=None, delay=0):
    requests = []
    payload = json.dumps(body if body is not None else choice()).encode() if raw is None else raw

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            received = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            requests.append({"path": self.path, "method": self.command,
                             "headers": dict(self.headers), "body": json.loads(received) if received else None})
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
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class JevClientTests(unittest.TestCase):
    def assert_closed(self, result, code):
        self.assertEqual(result["value"], "hold")
        self.assertTrue(result["abstained"])
        self.assertFalse(result["calibrated"])
        self.assertEqual(result["confidence"], 0)
        self.assertEqual(result["probability_source"], "fail_closed_policy")
        self.assertEqual(result["probabilities"], {"buy": 0, "sell": 0, "hold": 1})
        self.assertEqual(result["error_code"], code)

    def test_http_contract_and_snapshot_preserve_evidence_without_future_data(self):
        with endpoint() as (url, requests):
            result = JevClient(url, KEY).judge(signal(), bar())
        self.assertEqual(result["value"], "buy")
        request = requests[0]
        self.assertEqual((request["method"], request["path"]), ("POST", "/v1/systemone"))
        self.assertEqual(request["headers"]["Authorization"], f"Bearer {KEY}")
        self.assertEqual(request["headers"]["Content-Type"], "application/json")
        body = request["body"]
        self.assertEqual(set(body), {"model", "state", "questions"})
        self.assertEqual(body["model"], "jev-1.14.0")
        self.assertEqual(set(body["questions"]), {"direction"})
        question = body["questions"]["direction"]
        self.assertEqual(question["type"], "choice")
        self.assertEqual(set(question["criteria"]), {"buy", "sell", "hold"})
        state = body["state"]
        self.assertEqual(set(state), {"decision_time", "signal", "completed_bar"})
        self.assertEqual(state["decision_time"], "2026-11-13T10:00:00Z")
        self.assertEqual(state["completed_bar"]["close"], 101)
        self.assertEqual(state["signal"]["evidence"][0]["quote"], signal().evidence[0].quote)
        self.assertNotIn(KEY, json.dumps(body))
        self.assertNotIn("profit_probability", result)

    def test_provider_confidence_and_selected_probability_remain_distinct(self):
        with endpoint() as (url, _):
            result = JevClient(url, KEY).judge(signal(), bar())
        self.assertEqual(result["confidence"], 0.8)
        self.assertEqual(result["confidence_basis"], "selected_label_probability")
        self.assertEqual(result["provider_confidence"], 0.7)
        self.assertFalse(result["abstained"])
        self.assertFalse(result["calibrated"])
        self.assertEqual(result["calibration_source"], "provider_claim_not_locally_validated")
        self.assertEqual(result["probability_source"], "jev_model")
        self.assertEqual(result["provider"], "typesafe")
        self.assertEqual(result["usage"], {"input_tokens": 350, "output_tokens": 30})

    def test_environment_configuration_and_explicit_model_pin_reach_http_service(self):
        with endpoint(choice(model="jev-1.13.0")) as (url, requests):
            with patch.dict(os.environ, {"TYPESAFE_API_KEY": KEY, "TYPESAFE_BASE_URL": url}):
                result = JevClient(model="jev-1.13.0").judge(signal(), bar())
        self.assertEqual(result["model"], "jev-1.13.0")
        self.assertEqual(requests[0]["body"]["model"], "jev-1.13.0")
        self.assertEqual(requests[0]["headers"]["Authorization"], f"Bearer {KEY}")

    def test_explicit_configuration_overrides_environment(self):
        with endpoint() as (url, requests):
            with patch.dict(os.environ, {"TYPESAFE_API_KEY": "other-key",
                                         "TYPESAFE_BASE_URL": "https://invalid.example"}):
                result = JevClient(url, KEY).judge(signal(), bar())
        self.assertEqual(result["value"], "buy")
        self.assertEqual(requests[0]["headers"]["Authorization"], f"Bearer {KEY}")

    def test_missing_credential_abstains_without_sending_evidence(self):
        with endpoint() as (url, requests), patch.dict(os.environ, {}, clear=True):
            result = JevClient(url).judge(signal(), bar())
        self.assert_closed(result, "missing_api_key")
        self.assertEqual(requests, [])

    def test_future_expired_and_different_asset_candidates_are_not_sent(self):
        cases = [
            (replace(signal(), available_at=NOW + timedelta(seconds=1)), "future_signal"),
            (replace(signal(), expires_at=NOW), "expired_signal"),
            (replace(signal(), asset="OTHER"), "asset_mismatch"),
        ]
        with endpoint() as (url, requests):
            for candidate, code in cases:
                with self.subTest(code=code):
                    self.assert_closed(JevClient(url, KEY).judge(candidate, bar()), code)
        self.assertEqual(requests, [])

    def test_candidate_available_exactly_at_close_can_be_judged(self):
        with endpoint() as (url, requests):
            result = JevClient(url, KEY).judge(replace(signal(), available_at=NOW), bar())
        self.assertEqual(result["value"], "buy")
        self.assertEqual(len(requests), 1)

    def test_opposite_direction_is_vetoed_and_original_model_evidence_is_preserved(self):
        for side, value in (("long", "sell"), ("short", "buy"), ("none", "buy")):
            with self.subTest(side=side, value=value), endpoint(choice(value)) as (url, _):
                result = JevClient(url, KEY).judge(replace(signal(), side=side), bar())
            self.assert_closed(result, "opposite_direction")
            self.assertEqual(result["model_decision"]["value"], value)
            self.assertEqual(result["model_decision"]["provider_confidence"], 0.7)
            self.assertEqual(result["model_decision"]["probability_source"], "jev_model")

    def test_valid_short_and_model_hold_are_not_converted_into_transport_failures(self):
        for side, value in (("short", "sell"), ("long", "hold"), ("none", "hold")):
            with self.subTest(side=side, value=value), endpoint(choice(value)) as (url, _):
                result = JevClient(url, KEY).judge(replace(signal(), side=side), bar())
            self.assertEqual(result["value"], value)
            self.assertFalse(result["abstained"])
            self.assertNotIn("error_code", result)

    def test_valid_http_model_agreement_allows_entry_and_hold_vetoes_it_in_replay(self):
        following = Bar("BTCUSDT", NOW, NOW + timedelta(minutes=5), 101, 111, 100, 110)
        bars = [bar(), following]
        policy = Policy(fee_bps=0, slippage_bps=0)
        baseline = run_replay([signal()], bars, policy)
        self.assertEqual(baseline["summary"]["entries"], 1)
        for value, expected_entries, reason in (("buy", 1, "model_agreed"),
                                                ("hold", 0, "model_disagreement")):
            with self.subTest(value=value), endpoint(choice(value)) as (url, requests):
                result = run_replay([signal()], bars, policy, judge=JevClient(url, KEY).judge)
            self.assertEqual(result["summary"]["entries"], expected_entries)
            self.assertGreaterEqual(len(requests), 1)
            self.assertIn(reason, [reason for event in result["events"] for reason in event.get("reasons", [])])

    def test_cli_demo_uses_jev_http_and_saves_both_scores_and_provenance(self):
        with endpoint() as (url, requests), tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch.dict(os.environ, {"TYPESAFE_API_KEY": KEY, "TYPESAFE_BASE_URL": url,
                                         "TYPESAFE_MODEL": MODEL}), redirect_stdout(output):
                status = main(["demo", "--judge", "jev", "--out", directory, "--format", "json"])
            bundle = json.loads((Path(directory) / "run.json").read_text())
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(output.getvalue())["entries"], 1)
        self.assertEqual(bundle["replay"]["summary"]["entries"], 1)
        self.assertEqual(len(requests), 1)
        self.assertEqual(requests[0]["path"], "/v1/systemone")
        self.assertEqual(requests[0]["body"]["model"], MODEL)
        event = next(event for event in bundle["replay"]["events"] if event["type"] == "model_judgment")
        self.assertEqual(event["reasons"], ["model_agreed"])
        self.assertEqual(event["confidence"], 0.8)
        self.assertEqual(event["provider_confidence"], 0.7)
        self.assertEqual(event["model"], MODEL)
        self.assertEqual(event["provider"], "typesafe")
        self.assertEqual(event["probability_source"], "jev_model")
        self.assertEqual(event["calibration_source"], "provider_claim_not_locally_validated")
        self.assertFalse(event["calibrated"])
        self.assertNotIn(KEY, json.dumps(bundle))

    def test_cli_missing_key_saves_explicit_abstention_without_network(self):
        with endpoint() as (url, requests), tempfile.TemporaryDirectory() as directory:
            output = io.StringIO()
            with patch.dict(os.environ, {"TYPESAFE_BASE_URL": url}, clear=True), redirect_stdout(output):
                status = main(["demo", "--judge", "jev", "--out", directory, "--format", "json"])
            bundle = json.loads((Path(directory) / "run.json").read_text())
        self.assertEqual(status, 0)
        self.assertEqual(requests, [])
        self.assertEqual(json.loads(output.getvalue())["entries"], 0)
        self.assertEqual(bundle["replay"]["summary"]["entries"], 0)
        event = next(event for event in bundle["replay"]["events"] if event["type"] == "model_judgment")
        self.assertEqual(event["reasons"], ["model_policy_abstention"])
        self.assertEqual(event["error_code"], "missing_api_key")
        self.assertEqual(event["probability_source"], "fail_closed_policy")

    def test_malformed_probability_distributions_fail_closed(self):
        cases = [
            {"buy": 0.8, "hold": 0.2},
            {"buy": 0.8, "sell": 0.1, "hold": 0.1, "other": 0},
            {"buy": 0.8, "sell": 0.2, "hold": 0.2},
            {"buy": float("nan"), "sell": 0, "hold": 0},
            {"buy": float("inf"), "sell": 0, "hold": 0},
            {"buy": 1.1, "sell": -0.1, "hold": 0},
            {"buy": True, "sell": 0, "hold": 0},
            {"buy": "0.8", "sell": 0.1, "hold": 0.1},
            {"buy": 10 ** 400, "sell": 0, "hold": 0},
            {"buy": 0.1, "sell": 0.8, "hold": 0.1},
        ]
        for probabilities in cases:
            with self.subTest(probabilities=probabilities), endpoint(choice(probabilities=probabilities)) as (url, _):
                self.assert_closed(JevClient(url, KEY).judge(signal(), bar()), "malformed_response")

    def test_invalid_answer_or_model_metadata_fails_closed(self):
        cases = [
            choice(model="jev-latest"), choice(model="jev-1.13.0"),
            choice(type="noul"), choice(choice="wait"), choice(choice=[]),
            choice(confidence=None), choice(confidence=True), choice(confidence="0.7"),
            choice(confidence=-0.1), choice(confidence=float("nan")),
            {**choice(), "answers": {}},
            {**choice(), "answers": {"wrong_id": choice()["answers"]["direction"]}},
            {**choice(), "answers": {"direction": []}},
            {**choice(), "usage": {"input_tokens": True, "output_tokens": 0}},
            {**choice(), "usage": {"input_tokens": 10, "output_tokens": -1}},
            {**choice(), "usage": None},
            [], None,
        ]
        for body in cases:
            with self.subTest(body=body), endpoint(raw=json.dumps(body).encode()) as (url, _):
                self.assert_closed(JevClient(url, KEY).judge(signal(), bar()), "malformed_response")

    def test_duplicate_json_keys_invalid_encoding_and_large_responses_fail_closed(self):
        valid = json.dumps(choice()).encode()
        cases = [valid.replace(b'"choice": "buy"', b'"choice": "sell", "choice": "buy"'),
                 b"not JSON", b"\xff", b" " * 1_048_577, b"[" * 2000]
        for raw in cases:
            with self.subTest(prefix=raw[:30]), endpoint(raw=raw) as (url, _):
                self.assert_closed(JevClient(url, KEY).judge(signal(), bar()), "malformed_response")

    def test_http_errors_do_not_retry_or_leak_server_bodies_and_secrets(self):
        for status in (401, 402, 422, 429, 500, 529):
            with self.subTest(status=status), endpoint(status=status, raw=("private " + KEY).encode()) as (url, requests):
                result = JevClient(url, KEY).judge(signal(), bar())
            self.assert_closed(result, "http_error")
            self.assertIn(str(status), result["error"])
            self.assertNotIn(KEY, json.dumps(result))
            self.assertNotIn("private", json.dumps(result))
            self.assertEqual(len(requests), 1)

    def test_redirect_does_not_forward_credentials_or_evidence(self):
        with endpoint(status=303, headers={"Location": "/elsewhere"}) as (url, requests):
            result = JevClient(url, KEY).judge(signal(), bar())
        self.assert_closed(result, "http_error")
        self.assertEqual(len(requests), 1)

    def test_connection_failure_and_timeout_abstain(self):
        with socket.socket() as reserved:
            reserved.bind(("127.0.0.1", 0))
            # The port is reserved but is not listening.
            url = f"http://127.0.0.1:{reserved.getsockname()[1]}"
            self.assert_closed(JevClient(url, KEY, timeout=0.1).judge(signal(), bar()), "unavailable")
        with endpoint(delay=0.1) as (url, requests):
            result = JevClient(url, KEY, timeout=0.02).judge(signal(), bar())
        self.assert_closed(result, "unavailable")
        self.assertEqual(len(requests), 1)

    def test_invalid_configuration_is_rejected_before_any_request(self):
        cases = [
            {"base_url": "http://api.typesafe.ai"}, {"base_url": "ftp://api.typesafe.ai"},
            {"base_url": "https://user:password@api.typesafe.ai"},
            {"base_url": "https://api.typesafe.ai?key=secret"},
            {"base_url": "https://api.typesafe.ai#fragment"},
            {"base_url": "https://api.typesafe.ai\n"}, {"base_url": "https://api.typesafe.ai:invalid"},
            {"api_key": "key\nheader"}, {"api_key": ""}, {"api_key": "non ascii \u00e4"},
            {"model": "jev-latest"}, {"model": "jev-preview"}, {"model": "different-model"},
            {"timeout": 0}, {"timeout": True}, {"timeout": float("nan")},
        ]
        for kwargs in cases:
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                JevClient(**kwargs)


if __name__ == "__main__":
    unittest.main()
