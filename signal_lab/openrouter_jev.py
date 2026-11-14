"""Bounded Choice requests to Jev through OpenRouter's Decisions API.

Contract: https://openrouter.ai/docs/api/api-reference/alphadecisions/submit-a-decisions-request
Model catalog: https://openrouter.ai/api/v1/models?output_modalities=decisions
This client checks the transport and answer shapes. It does not validate the
meaning of a source, estimate trading returns, or place orders.
"""
from __future__ import annotations

from http.client import HTTPException
import json
import math
import os
import re
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener


REQUEST_MODEL = "typesafe/jev-1.14"
RESOLVED_MODEL = "typesafe/jev-1.14-20261014"
ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
MAX_INPUT_BYTES = 32_768
MAX_INPUT_BYTES_LIMIT = 262_144
MAX_RESPONSE_BYTES = 1_048_576


class _NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class _RequestTooLarge(ValueError):
    pass


def _unique_object(pairs: list[tuple[str, Any]]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError("Non-finite JSON number")


def _check_object_keys(value: Any) -> None:
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("JSON object keys must be strings")
        for child in value.values():
            _check_object_keys(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            _check_object_keys(child)


def _number(value: Any, *, unit: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Expected a number")
    if not math.isfinite(value) or value < 0 or (unit and value > 1):
        raise ValueError("Number outside the accepted range")
    return float(value)


def _questions(value: Any) -> dict[str, set[str]]:
    if not isinstance(value, dict) or not value:
        raise ValueError("Expected named Choice questions")
    labels = {}
    for name, question in value.items():
        if not isinstance(name, str) or not name.strip() or not isinstance(question, dict):
            raise ValueError("Invalid question")
        if set(question) != {"type", "instructions", "criteria"} or question["type"] != "choice":
            raise ValueError("Only Choice questions are supported")
        if not isinstance(question["instructions"], str) or not question["instructions"].strip():
            raise ValueError("Each question needs instructions")
        criteria = question["criteria"]
        if not isinstance(criteria, dict) or not 1 <= len(criteria) <= 255:
            raise ValueError("Each question needs one to 255 choices")
        if any(not isinstance(label, str) or not label.strip()
               or not isinstance(description, str) or not description.strip()
               for label, description in criteria.items()):
            raise ValueError("Choice labels and descriptions must be non-empty strings")
        labels[name] = set(criteria)
    return labels


class OpenRouterJevClient:
    """Send one bounded request and return checked answers or an explicit error.

    The production destination is fixed. ``endpoint`` permits a loopback server
    for transport tests, never another remote host. No automatic retries occur:
    a timeout can follow a billed request, so the caller owns any retry decision.

    ``max_input_bytes`` bounds the entire UTF-8 request, including questions.
    The default keeps requests short; it is not a token or billing estimate.
    A caller must enforce its own total cost budget and stop on unknown costs.
    """

    def __init__(
        self,
        api_key: str | None = None,
        *,
        model: str = REQUEST_MODEL,
        expected_model: str = RESOLVED_MODEL,
        timeout: float = 30,
        max_input_bytes: int = MAX_INPUT_BYTES,
        max_response_bytes: int = MAX_RESPONSE_BYTES,
        endpoint: str = ENDPOINT,
    ) -> None:
        if not isinstance(model, str) or re.fullmatch(r"typesafe/jev-[0-9]+\.[0-9]+", model) is None:
            raise ValueError("model must name an explicit OpenRouter Jev version")
        if not isinstance(expected_model, str) or re.fullmatch(re.escape(model) + r"-[0-9]{8}", expected_model) is None:
            raise ValueError("expected_model must pin the requested Jev version's canonical snapshot")
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("timeout must be a finite positive number")
        for name, value in (("max_input_bytes", max_input_bytes), ("max_response_bytes", max_response_bytes)):
            if type(value) is not int or value <= 0:
                raise ValueError(f"{name} must be a positive integer")
        if max_input_bytes > MAX_INPUT_BYTES_LIMIT:
            raise ValueError("max_input_bytes exceeds this client's 262144-byte request ceiling")
        if not isinstance(endpoint, str) or any(character.isspace() or ord(character) < 32 for character in endpoint):
            raise ValueError("endpoint must be the OpenRouter Decisions URL or a loopback test server")
        parsed = urlsplit(endpoint)
        try:
            port = parsed.port
        except ValueError:
            raise ValueError("Invalid endpoint port") from None
        local_test = (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1"}
                      and port is not None and parsed.path == "/api/alpha/decisions")
        if ((endpoint != ENDPOINT and not local_test) or parsed.username is not None
                or parsed.password is not None or parsed.query or parsed.fragment):
            raise ValueError("endpoint must be the OpenRouter Decisions URL or a loopback test server")
        if api_key is None:
            api_key = os.environ.get("OPENROUTER_API_KEY")
        if api_key is not None and (not isinstance(api_key, str) or not api_key
                                   or any(not 33 <= ord(character) <= 126 for character in api_key)):
            raise ValueError("api_key must be a non-empty ASCII string without whitespace")
        self._api_key = api_key
        self.model = model
        self.expected_model = expected_model
        self.timeout = float(timeout)
        self.max_input_bytes = max_input_bytes
        self.max_response_bytes = max_response_bytes
        self.endpoint = endpoint
        self._opener = build_opener(_NoRedirects())

    @property
    def configured(self) -> bool:
        """Whether a credential was supplied, without exposing its value."""
        return self._api_key is not None

    def _prepare(self, state: Any, questions: Any) -> tuple[bytes, dict[str, set[str]]]:
        try:
            requested = _questions(questions)
            if not isinstance(state, (str, dict, list)):
                raise ValueError("state must be text, an object, or an array")
            _check_object_keys(state)
            payload = json.dumps({"model": self.model, "state": state, "questions": questions},
                                 ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
        except (ValueError, TypeError, UnicodeError, RecursionError, OverflowError):
            raise ValueError("State or questions do not satisfy the Choice request contract") from None
        if len(payload) > self.max_input_bytes:
            raise _RequestTooLarge("Request exceeds the configured UTF-8 byte limit")
        return payload, requested

    def preflight(self, state: Any, questions: Any) -> dict:
        """Validate the full request without a credential or network operation.

        Return its byte size and destination identity, without copying source
        text or credentials. Invalid and oversized requests raise ``ValueError``.
        The reported size is not a token count or a billing estimate.
        """
        payload, _ = self._prepare(state, questions)
        return {
            "request_bytes": len(payload),
            "endpoint": self.endpoint,
            "transport": "openrouter" if self.endpoint == ENDPOINT else "loopback_test",
            "request_model": self.model,
            "expected_model": self.expected_model,
        }

    def _failure(self, code: str, message: str, *, sent: bool, started: float, status: int | None = None) -> dict:
        result = {
            "ok": False,
            "answers": {},
            "request_model": self.model,
            "expected_model": self.expected_model,
            "model": None,
            "provider": None,
            "request_id": None,
            "usage": None,
            "request_sent": sent,
            "cost_known": not sent,
            "error_code": code,
            "error": message,
            "latency_ms": round((time.monotonic() - started) * 1000, 3),
        }
        if status is not None:
            result["http_status"] = status
        return result

    def _validate(self, body: Any, requested: dict[str, set[str]]) -> dict:
        if not isinstance(body, dict) or body.get("model") != self.expected_model:
            raise ValueError("Unexpected model snapshot")
        if body.get("provider") != "TypeSafe":
            raise ValueError("Unexpected provider")
        request_id = body.get("id")
        if not isinstance(request_id, str) or re.fullmatch(r"[A-Za-z0-9_-]{1,200}", request_id) is None:
            raise ValueError("Missing or invalid request identifier")
        if self._api_key and self._api_key in request_id:
            raise ValueError("Response identifier contains credential data")
        answers = body.get("answers")
        if not isinstance(answers, dict) or set(answers) != set(requested):
            raise ValueError("Response question set differs from request")
        checked = {}
        for name, labels in requested.items():
            answer = answers[name]
            if not isinstance(answer, dict) or answer.get("type") != "choice":
                raise ValueError("Expected a Choice answer")
            selected = answer.get("choice")
            if not isinstance(selected, str) or selected not in labels:
                raise ValueError("Unknown selected choice")
            probabilities = answer.get("probabilities")
            if not isinstance(probabilities, dict) or set(probabilities) != labels:
                raise ValueError("Response choice set differs from request")
            probabilities = {label: _number(probability, unit=True) for label, probability in probabilities.items()}
            if not math.isclose(math.fsum(probabilities.values()), 1, rel_tol=0, abs_tol=1e-6):
                raise ValueError("Choice probabilities must sum to one")
            if probabilities[selected] + 1e-9 < max(probabilities.values()):
                raise ValueError("Selected choice does not have the largest probability")
            checked[name] = {"type": "choice", "choice": selected,
                             "probabilities": probabilities, "confidence": _number(answer.get("confidence"), unit=True)}
        usage = body.get("usage")
        if not isinstance(usage, dict):
            raise ValueError("Missing usage")
        for field in ("input_tokens", "output_tokens"):
            if type(usage.get(field)) is not int or usage[field] < 0:
                raise ValueError("Invalid token usage")
        cost = _number(usage.get("cost"))
        return {
            "ok": True,
            "answers": checked,
            "request_model": self.model,
            "expected_model": self.expected_model,
            "model": body["model"],
            "provider": "TypeSafe",
            "request_id": request_id,
            "usage": {"input_tokens": usage["input_tokens"], "output_tokens": usage["output_tokens"], "cost": cost},
            "request_sent": True,
            "cost_known": True,
        }

    def decide(self, state: Any, questions: Any) -> dict:
        """Evaluate named Choice questions without inventing answers on failure."""
        started = time.monotonic()
        try:
            payload, requested = self._prepare(state, questions)
        except _RequestTooLarge:
            return self._failure("request_too_large", "Request exceeds the configured UTF-8 byte limit",
                                 sent=False, started=started)
        except ValueError:
            return self._failure("invalid_request", "State or questions do not satisfy the Choice request contract",
                                 sent=False, started=started)
        if self._api_key is None:
            return self._failure("missing_api_key", "OPENROUTER_API_KEY is not configured",
                                 sent=False, started=started)
        request = Request(self.endpoint, data=payload, method="POST",
                          headers={"Content-Type": "application/json", "Accept": "application/json",
                                   "Authorization": f"Bearer {self._api_key}"})
        try:
            with self._opener.open(request, timeout=self.timeout) as response:
                raw = response.read(self.max_response_bytes + 1)
            if len(raw) > self.max_response_bytes:
                return self._failure("response_too_large", "Response exceeds the configured byte limit",
                                     sent=True, started=started)
            body = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object, parse_constant=_invalid_constant)
            result = self._validate(body, requested)
        except HTTPError as error:
            status = error.code
            error.close()
            return self._failure("http_error", "OpenRouter returned an unsuccessful HTTP status",
                                 sent=True, started=started, status=status)
        except (URLError, TimeoutError, OSError, HTTPException):
            return self._failure("unavailable", "OpenRouter is unavailable or the request timed out",
                                 sent=True, started=started)
        except (ValueError, TypeError, KeyError, UnicodeError, RecursionError, OverflowError):
            return self._failure("malformed_response", "Response failed the pinned OpenRouter Choice contract",
                                 sent=True, started=started)
        result["latency_ms"] = round((time.monotonic() - started) * 1000, 3)
        return result
