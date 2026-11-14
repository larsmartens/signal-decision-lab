#!/usr/bin/env python3
"""Validate claim evidence and Jev request sizes without credentials or model calls."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from signal_lab.claim_manifest import load_review_inputs  # noqa: E402
from signal_lab.openrouter_jev import OpenRouterJevClient  # noqa: E402
from signal_lab.semantic_claims import prepare_state, review_questions  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims", required=True, help="Public claim manifest or private contextual annotations")
    parser.add_argument("--transcripts", required=True, help="Exact canonical transcript JSON directory")
    args = parser.parse_args(argv)
    try:
        _, claims, transcripts = load_review_inputs(args.claims, args.transcripts)
        client = OpenRouterJevClient()
        questions = review_questions()
        sizes = [client.preflight(prepare_state(claim, transcripts[claim.source_id]), questions)["request_bytes"]
                 for claim in claims]
        print(json.dumps({"status": "validated", "claims": len(claims), "sources": len(transcripts),
                          "maximum_request_bytes": max(sizes), "model_requests": 0,
                          "scope": "Schema, exact source evidence and request bounds; semantic fidelity is not measured."}))
        return 0
    except (ValueError, OSError, RuntimeError, KeyError, TypeError):
        print(json.dumps({"status": "error", "error_code": "invalid_claim_input", "model_requests": 0,
                          "error": "Claim validation failed; check the manifest, source hashes, evidence offsets and request sizes."}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
