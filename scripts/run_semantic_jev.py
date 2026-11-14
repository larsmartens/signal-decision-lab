#!/usr/bin/env python3
"""Review contextual Krown interpretations through Jev with explicit request bounds."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from signal_lab.claim_manifest import load_review_inputs  # noqa: E402
from signal_lab.openrouter_jev import OpenRouterJevClient  # noqa: E402
from signal_lab.semantic_claims import MissingCredentialError, run_semantic_review  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claims", required=True, help="Public claim manifest or private contextual annotations")
    parser.add_argument("--transcripts", required=True, help="Directory of canonical timestamped transcript JSON")
    parser.add_argument("--out", required=True, help="Fixed experiment directory; matching completed requests resume from cache")
    parser.add_argument("--max-requests", type=int, default=12, help="Maximum reserved requests over the entire saved run")
    parser.add_argument("--cost-stop-usd", type=float, default=1,
                        help="Stop after observed spend reaches this value; a provider key cap is needed for a hard billing limit")
    parser.add_argument("--minimum-probability", type=float, default=.8,
                        help="Fixed selected-answer threshold; calibration on this task is unmeasured")
    args = parser.parse_args(argv)
    try:
        selection, claims, transcripts = load_review_inputs(args.claims, args.transcripts)
        result = run_semantic_review(claims, transcripts, OpenRouterJevClient(), args.out,
                                     selection_basis=selection, max_requests=args.max_requests,
                                     cost_stop_usd=args.cost_stop_usd, minimum_probability=args.minimum_probability)
        print(json.dumps({key: value for key, value in result.items() if key != "results"}, allow_nan=False))
        return 0 if result["status"] == "complete" else 1
    except MissingCredentialError:
        print(json.dumps({"status": "error", "error_code": "missing_api_key",
                          "error": "OPENROUTER_API_KEY is not configured; no model review was run."}))
        return 1
    except (ValueError, OSError, RuntimeError, KeyError, TypeError):
        # A provider implementation or malformed input may contain private text.
        # Only the known local validation error is safe to show; never dump secrets.
        print(json.dumps({"status": "error", "error": "Semantic review failed; check credentials, input evidence, protocol and request limits."}))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
