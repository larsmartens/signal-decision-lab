"""Check semantic evidence boundaries, paid-call limits and honest resume behavior."""
from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import tempfile
import threading
import unittest

from signal_lab.models import Evidence, Segment, Transcript, jsonable
from signal_lab.openrouter_jev import OpenRouterJevClient, REQUEST_MODEL, RESOLVED_MODEL
from signal_lab.semantic_claims import (
    GroundedField, MissingCredentialError, SemanticClaim, fidelity_verdict, load_claims,
    prepare_state, review_questions, run_semantic_review,
)


CAPTURED = datetime(2026, 11, 13, 22, tzinfo=timezone.utc)
AUTHORED = datetime(2026, 11, 14, 0, tzinfo=timezone.utc)
NOW = datetime(2026, 11, 14, 1, tzinfo=timezone.utc)


def source() -> Transcript:
    return Transcript(
        source_id="context-source", channel="Synthetic fixture", url="https://example.com/fixture",
        published_at=datetime(2026, 11, 12, 20, tzinfo=timezone.utc), available_at=CAPTURED,
        kind="synthetic", segments=(
            Segment("s1", 0, 8, "That ends the Bitcoin discussion."),
            Segment("s2", 8, 18, "The next question is about MSTZ, not Bitcoin's price."),
            Segment("s3", 18, 28, "If MSTZ closes above 12 on a weekly basis, I would look for 15."),
            Segment("s4", 28, 38, "Until that weekly close happens, this is only a conditional scenario."),
            Segment("s5", 38, 48, "A weekly close below 10 would invalidate that scenario."),
            Segment("s6", 48, 58, "I have not said how long the move would take."),
            Segment("s7", 58, 68, "Let us turn to another instrument now."),
        ),
    )


def field(value: str | None, segment_id: str | None = None, quote: str | None = None) -> GroundedField:
    return GroundedField(value, (Evidence(segment_id, quote),) if segment_id and quote else ())


def candidate(identifier: str = "mstz-conditional") -> SemanticClaim:
    return SemanticClaim(
        id=identifier, source_id="context-source", first_segment_id="s2", last_segment_id="s6",
        ticker=field("MSTZ", "s2", "The next question is about MSTZ, not Bitcoin's price."),
        stance="conditional",
        expected_move=field("A possible rise toward 15 after the weekly close condition.", "s3",
                            "If MSTZ closes above 12 on a weekly basis, I would look for 15."),
        conditions=(field("MSTZ must close above 12 on a weekly basis.", "s3",
                          "If MSTZ closes above 12 on a weekly basis, I would look for 15."),),
        invalidation=field("A weekly close below 10.", "s5", "A weekly close below 10 would invalidate that scenario."),
        timeframe=field(None), targets=(field("15", "s3", "I would look for 15."),),
        interpretation="The candle interval belongs to the prerequisite. The move's horizon is unknown.",
        author_kind="assistant", author_name="Fixture contextual reader", created_at=AUTHORED,
    )


def provider_result(questions: dict, *, cost: float = .001, overrides: dict | None = None) -> dict:
    answers = {
        name: {"type": "choice", "choice": "faithful", "confidence": .85,
               "probabilities": {"faithful": .9, "unsupported": .05, "unclear": .05}}
        for name in questions
    }
    for name, value in (overrides or {}).items():
        answers[name] = value
    return {"ok": True, "answers": answers, "request_model": REQUEST_MODEL, "model": RESOLVED_MODEL,
            "provider": "TypeSafe", "request_id": "gen-semantic-test", "latency_ms": 12.5,
            "request_sent": True, "cost_known": True,
            "usage": {"input_tokens": 1_000, "output_tokens": 40, "cost": cost}}


class Client:
    configured = True
    model = REQUEST_MODEL
    expected_model = RESOLVED_MODEL
    endpoint = "http://127.0.0.1:1/api/alpha/decisions"

    def __init__(self, responses: list | None = None):
        self.calls: list[dict] = []
        self.responses = list(responses or [])

    def preflight(self, state: dict, questions: dict) -> dict:
        return OpenRouterJevClient("test-only-credential", endpoint=self.endpoint).preflight(state, questions)

    def decide(self, state: dict, questions: dict) -> dict:
        self.calls.append({"state": deepcopy(state), "questions": deepcopy(questions)})
        response = self.responses.pop(0) if self.responses else provider_result(questions)
        if isinstance(response, BaseException):
            raise response
        return deepcopy(response)


def run(client: Client, out: Path, claims: list[SemanticClaim] | None = None, **kwargs) -> dict:
    return run_semantic_review(claims or [candidate()], {"context-source": source()}, client, out,
                               selection_basis="A synthetic passage selected to test subject and conditional meaning.",
                               clock=lambda: NOW, **kwargs)


@contextmanager
def http_provider():
    requests = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append(body)
            result = provider_result(body["questions"])
            wire = {"model": result["model"], "provider": result["provider"], "id": result["request_id"],
                    "answers": result["answers"], "usage": result["usage"]}
            payload = json.dumps(wire).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=lambda: server.serve_forever(poll_interval=.01), daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}/api/alpha/decisions", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class ContextualClaimTests(unittest.TestCase):
    def test_round_trip_preserves_unknowns_and_separates_author_from_source(self):
        original = candidate()
        restored = SemanticClaim.from_dict(json.loads(json.dumps(original.to_dict())))
        self.assertEqual(restored, original)
        self.assertIsNone(restored.timeframe.value)
        self.assertEqual(restored.timeframe.evidence, ())
        self.assertEqual(restored.author_kind, "assistant")
        self.assertEqual(restored.ticker.value, "MSTZ")

    def test_fields_require_explicit_unknown_or_exact_evidence(self):
        for value in ({"value": "82,000", "evidence": []},
                      {"value": None, "evidence": [{"segment_id": "s1", "quote": "x"}]},
                      {"value": "82,000"},
                      {"value": "82,000", "evidence": [], "reviewed": True}):
            with self.subTest(value=value), self.assertRaises(ValueError):
                GroundedField.from_dict(value)
        unknown = GroundedField.from_dict({"value": None, "evidence": []})
        self.assertIsNone(unknown.value)

    def test_unknown_ticker_is_preserved_without_nearby_bitcoin_substitution(self):
        claim = replace(candidate(), ticker=field(None))
        state = prepare_state(claim, source())
        self.assertIsNone(state["candidate_interpretation"]["ticker"]["value"])
        self.assertIn("Bitcoin", state["caption_context"]["segments"][0]["text"])

    def test_context_includes_neighboring_captions_and_original_capture_time(self):
        state = prepare_state(candidate(), source())
        self.assertEqual([item["id"] for item in state["caption_context"]["segments"]],
                         ["s1", "s2", "s3", "s4", "s5", "s6", "s7"])
        self.assertEqual(state["source"]["captions_available_at"], jsonable(CAPTURED))
        self.assertEqual(state["candidate_interpretation"]["stance"], "conditional")
        self.assertNotIn("prices", state)
        self.assertNotIn("future_returns", state)

    def test_grounding_rejects_fabricated_quote_wrong_source_and_reversed_context(self):
        bad = [replace(candidate(), ticker=field("BTC", "s2", "This is a Bitcoin long.")),
               replace(candidate(), source_id="different-source"),
               replace(candidate(), first_segment_id="s6", last_segment_id="s2"),
               replace(candidate(), first_segment_id="s3"),
               replace(candidate(), last_segment_id="missing"),
               replace(candidate(), created_at=source().published_at)]
        for claim in bad:
            with self.subTest(claim=claim), self.assertRaises(ValueError):
                prepare_state(claim, source())

    def test_context_is_rejected_instead_of_silently_truncated(self):
        with self.assertRaisesRegex(ValueError, "exceeds the byte limit"):
            prepare_state(candidate(), source(), max_context_bytes=30)

    def test_unknown_claim_fields_and_duplicate_json_cannot_hide_interpretation_changes(self):
        data = candidate().to_dict()
        data["reviewed"] = True
        with self.assertRaises(ValueError):
            SemanticClaim.from_dict(data)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "claims.json"
            path.write_text('{"schema_version":1,"schema_version":2,"selection_basis":"x","claims":[]}')
            with self.assertRaisesRegex(ValueError, "Duplicate JSON"):
                load_claims(path)

    def test_every_claim_field_has_a_semantic_check_without_a_trading_action(self):
        questions = review_questions()
        self.assertEqual(set(questions), {"subject", "expected_move", "stance", "conditions",
                                          "invalidation", "timeframe", "targets", "context"})
        for question in questions.values():
            self.assertEqual(set(question["criteria"]), {"faithful", "unsupported", "unclear"})
            self.assertIn("untrusted data", question["instructions"])
            self.assertIn("Do not forecast prices", question["instructions"])

    def test_unsupported_subject_or_low_confidence_does_not_become_model_supported(self):
        result = provider_result(review_questions())
        result["answers"]["subject"] = {"type": "choice", "choice": "unsupported", "confidence": .85,
                                        "probabilities": {"faithful": .05, "unsupported": .9, "unclear": .05}}
        verdict = fidelity_verdict(result["answers"])
        self.assertEqual(verdict["verdict"], "model_disagreed")
        self.assertEqual(verdict["unsupported_fields"], ["subject"])
        result["answers"]["subject"] = {"type": "choice", "choice": "faithful", "confidence": .1,
                                        "probabilities": {"faithful": .4, "unsupported": .3, "unclear": .3}}
        self.assertEqual(fidelity_verdict(result["answers"])["verdict"], "uncertain")
        with self.assertRaises(ValueError):
            fidelity_verdict({})


class BoundedSemanticRunTests(unittest.TestCase):
    def test_success_records_usage_and_resumes_without_another_model_call(self):
        client = Client()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = run(client, root)
            second = run(client, root)
            self.assertEqual(len(client.calls), 1)
            self.assertEqual(first["status"], "complete")
            self.assertEqual(first["http_attempts"], 1)
            self.assertEqual(second["new_requests_this_invocation"], 0)
            self.assertEqual(second["cached_receipts_this_invocation"], 1)
            self.assertEqual(second["observed_cost_usd"], .001)
            self.assertEqual(second["input_tokens"], 1_000)
            result = second["results"][0]
            self.assertEqual(result["result"]["latency_ms"], 12.5)
            self.assertEqual(result["result"]["model"], RESOLVED_MODEL)
            self.assertEqual(result["assessment"]["verdict"], "model_supported")
            public = (root / "summary.json").read_text()
            self.assertNotIn('"quote":', public)
            self.assertNotIn('"segments":', public)
            self.assertNotIn('"reviewed":true', public)
            self.assertIn("quote_sha256", public)
            self.assertEqual(list(root.glob("**/*.tmp")), [])

    def test_actual_client_and_runner_use_the_same_question_contract_over_http(self):
        with http_provider() as (endpoint, requests), tempfile.TemporaryDirectory() as directory:
            client = OpenRouterJevClient("test-only-credential", endpoint=endpoint)
            result = run_semantic_review([candidate()], {"context-source": source()}, client, directory,
                                         selection_basis="Synthetic contract test", clock=lambda: NOW)
            self.assertEqual(result["status"], "complete")
            self.assertEqual(len(requests), 1)
            self.assertEqual(requests[0]["model"], REQUEST_MODEL)
            self.assertEqual(set(requests[0]["questions"]), set(review_questions()))
            self.assertEqual(requests[0]["state"]["candidate_interpretation"]["ticker"]["value"], "MSTZ")
            self.assertEqual(result["transport"], "loopback_test")
            self.assertEqual(result["endpoint"], endpoint)
            protocol = json.loads((Path(directory) / "protocol.json").read_text())
            self.assertEqual(protocol["endpoint"], endpoint)
            receipt = json.loads(next((Path(directory) / "requests").glob("*.json")).read_text())
            self.assertEqual(receipt["transport"], "loopback_test")
            self.assertEqual(receipt["endpoint"], endpoint)

    def test_later_oversized_request_prevents_the_entire_batch_from_spending(self):
        base = candidate()
        oversized = replace(candidate("second"), conditions=tuple(
            GroundedField(f"Condition {index}: " + "x" * 1900, base.conditions[0].evidence)
            for index in range(20)))
        with http_provider() as (endpoint, requests), tempfile.TemporaryDirectory() as directory:
            client = OpenRouterJevClient("test-only-credential", endpoint=endpoint)
            out = Path(directory) / "not-created"
            with self.assertRaises(ValueError):
                run_semantic_review([base, oversized], {"context-source": source()}, client, out,
                                    selection_basis="Synthetic oversized request test", clock=lambda: NOW)
            self.assertEqual(requests, [])
            self.assertFalse(out.exists())

    def test_transport_change_cannot_reuse_a_cached_model_review(self):
        client = Client()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            first = run(client, out)
            self.assertEqual(first["transport"], "loopback_test")
            client.endpoint = "https://openrouter.ai/api/alpha/decisions"
            with self.assertRaisesRegex(ValueError, "protocol differs"):
                run(client, out)
            self.assertEqual(len(client.calls), 1)

    def test_missing_key_is_an_error_before_any_run_is_created(self):
        client = Client()
        client.configured = False
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "not-created"
            with self.assertRaises(MissingCredentialError):
                run(client, out)
            self.assertFalse(out.exists())
            self.assertEqual(client.calls, [])

    def test_all_inputs_are_checked_before_the_first_paid_request(self):
        client = Client()
        invalid = replace(candidate("second"), ticker=field("BTC", "s2", "Invented source wording"))
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory) / "not-created"
            with self.assertRaises(ValueError):
                run(client, out, [candidate(), invalid])
            self.assertEqual(client.calls, [])
            self.assertFalse(out.exists())

    def test_request_cap_applies_across_resumes_and_cannot_be_silently_raised(self):
        client = Client()
        claims = [candidate(), candidate("second")]
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            first = run(client, out, claims, max_requests=1)
            second = run(client, out, claims, max_requests=1)
            self.assertEqual(first["status"], "request_limit_reached")
            self.assertEqual(second["status"], "request_limit_reached")
            self.assertEqual(len(client.calls), 1)
            self.assertEqual(second["completed_claims"], 1)
            with self.assertRaisesRegex(ValueError, "protocol differs"):
                run(client, out, claims, max_requests=2)
            self.assertEqual(len(client.calls), 1)

    def test_observed_cost_stop_is_recorded_as_a_stop_not_a_guaranteed_currency_cap(self):
        client = Client([provider_result(review_questions(), cost=.015)])
        claims = [candidate(), candidate("second")]
        with tempfile.TemporaryDirectory() as directory:
            first = run(client, Path(directory), claims, cost_stop_usd=.01)
            resumed = run(client, Path(directory), claims, cost_stop_usd=.01)
            self.assertEqual(first["status"], "observed_cost_stop_reached")
            self.assertEqual(resumed["status"], "observed_cost_stop_reached")
            self.assertEqual(len(client.calls), 1)
            self.assertEqual(first["observed_cost_usd"], .015)
            self.assertIn("not_a_hard_billing_limit", first["cost_stop_kind"])

    def test_unpriced_failure_blocks_later_requests_and_does_not_retry_on_resume(self):
        failure = {"ok": False, "answers": {}, "request_sent": True, "cost_known": False,
                   "usage": None, "error_code": "unavailable", "error": "Do not save this arbitrary body."}
        client = Client([failure])
        claims = [candidate(), candidate("second")]
        with tempfile.TemporaryDirectory() as directory:
            first = run(client, Path(directory), claims)
            resumed = run(client, Path(directory), claims)
            self.assertEqual(first["status"], "unpriced_request_requires_reconciliation")
            self.assertEqual(resumed["status"], first["status"])
            self.assertEqual(len(client.calls), 1)
            self.assertEqual(first["completed_claims"], 0)
            self.assertFalse(first["results"][0]["result"]["cost_known"])
            self.assertIsNone(first["results"][0]["result"]["usage"])
            self.assertNotIn("arbitrary body", json.dumps(first))
            self.assertNotIn("assessment", first["results"][0])

    def test_transport_exception_is_saved_without_its_secret_or_a_fabricated_answer(self):
        secret = "never-persist-this-secret"
        client = Client([RuntimeError(secret)])
        with tempfile.TemporaryDirectory() as directory:
            result = run(client, Path(directory))
            self.assertEqual(result["status"], "unpriced_request_requires_reconciliation")
            self.assertEqual(result["results"][0]["result"]["answers"], {})
            for path in Path(directory).rglob("*.json"):
                self.assertNotIn(secret, path.read_text())

    def test_crash_after_reservation_leaves_an_honest_unknown_outcome(self):
        client = Client([KeyboardInterrupt()])
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            with self.assertRaises(KeyboardInterrupt):
                run(client, out)
            resumed = run(client, out)
            self.assertEqual(resumed["status"], "interrupted_request_requires_reconciliation")
            self.assertEqual(resumed["reserved_requests"], 1)
            self.assertEqual(resumed["completed_claims"], 0)
            self.assertEqual(len(client.calls), 1)

    def test_changed_interpretation_or_threshold_requires_a_new_experiment(self):
        client = Client()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            run(client, out)
            for kwargs in ({"claims": [replace(candidate(), interpretation="A revised reading.")]},
                           {"minimum_probability": .7}):
                with self.assertRaisesRegex(ValueError, "protocol differs"):
                    run(client, out, **kwargs)
            self.assertEqual(len(client.calls), 1)

    def test_corrupt_cached_receipt_is_not_reused_or_requeried(self):
        client = Client()
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory)
            run(client, out)
            path = next((out / "requests").glob("*.json"))
            receipt = json.loads(path.read_text())
            receipt["result"]["usage"]["cost"] = 0
            path.write_text(json.dumps(receipt))
            with self.assertRaisesRegex(ValueError, "integrity check"):
                run(client, out)
            self.assertEqual(len(client.calls), 1)

    def test_forged_or_malformed_success_is_not_a_semantic_review(self):
        for change in ({"model": "wrong-model"}, {"answers": {}},
                       {"usage": {"input_tokens": 100, "output_tokens": 1, "cost": None}}):
            response = {**provider_result(review_questions()), **change}
            client = Client([response])
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                result = run(client, Path(directory))
                self.assertEqual(result["status"], "unpriced_request_requires_reconciliation")
                self.assertEqual(result["completed_claims"], 0)
                self.assertNotIn("assessment", result["results"][0])


if __name__ == "__main__":
    unittest.main()
