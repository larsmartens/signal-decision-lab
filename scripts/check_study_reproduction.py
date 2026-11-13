"""Compare an offline replay with the published experiment, without network access."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def check(expected: Path, actual: Path) -> dict:
    reference = json.loads((expected / "summary.json").read_text())
    replayed = json.loads((actual / "summary.json").read_text())
    for key in ("study_id", "coverage", "rows", "benchmark_rows", "literal_setup_coverage", "files"):
        if reference[key] != replayed[key]:
            raise ValueError(f"Published and replayed {key} differ")
    for relative, digest in reference["files"].items():
        for directory in (expected, actual):
            if hashlib.sha256((directory / relative).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Artifact checksum mismatch: {directory / relative}")
    return {"status": "identical", "strategy_runs": len(reference["rows"]),
            "benchmark_runs": len(reference["benchmark_rows"]), "checked_files": len(reference["files"])}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--expected", default="experiments/krown-20261114", type=Path)
    parser.add_argument("--actual", default="artifacts/krown-replay", type=Path)
    args = parser.parse_args()
    print(json.dumps(check(args.expected, args.actual)))


if __name__ == "__main__":
    main()
