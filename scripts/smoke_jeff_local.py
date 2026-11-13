#!/usr/bin/env python3
"""Run actual Jeff v1.4 locally; requires the separate environment in JEFF_SETUP.md.

The two original cases and six predeclared concise cases are representation
experiments, not a performance benchmark or evidence of profitable trading.
No vendor implementation is copied here.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict, replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from signal_lab.jeff import ADAPTER_VERSION, BASE_VERSION, CONTRACT_COMMIT, FUNCTION, JeffClient
from signal_lab.models import Bar, Evidence, Signal, jsonable


def make_signal() -> Signal:
    now = datetime(2026, 11, 13, 10, tzinfo=timezone.utc)
    return Signal(
        id="smoke-signal", source_id="synthetic-smoke", asset="TEST", side="long",
        statement_type="conditional", trigger="close_above", level=100,
        stop=95, target=110, timeframe_minutes=5, horizon_minutes=60,
        available_at=now-timedelta(minutes=10), expires_at=now+timedelta(minutes=60),
        evidence=(Evidence("segment-1", "Buy only after a five-minute close above 100."),),
        reviewed=True,
    )


def make_bar(close: float) -> Bar:
    now = datetime(2026, 11, 13, 10, tzinfo=timezone.utc)
    return Bar("TEST", now-timedelta(minutes=5), now, 100, 102, 98, close, 500)


def concise_call(signal: Signal, bar: Bar) -> dict:
    """One predeclared alternative; deliberately not the production payload."""
    desk = (
        "This desk evaluates a candidate entry direction from a reviewed signal. "
        "It does not size or execute orders. Use only the facts in market_state. "
        "Hold if the signal is unreviewed, not yet available, expired, or if its "
        "entry level or protective stop is missing. "
        "For close_above, the trigger is met only if the completed close is "
        "strictly greater than the entry level. For close_below, it is met only "
        "if the completed close is strictly less than the entry level. Equality "
        "does not meet either trigger. "
        "Buy if the trigger is met, the signal direction is long, and the "
        "protective stop is below the completed close. "
        "Sell if the trigger is met, the signal direction is short, and the "
        "protective stop is above the completed close. Otherwise hold. "
        "Position limits, order size, venue and execution are handled separately "
        "and are not conditions of this direction decision."
    )
    facts = (
        f"Decision time: {jsonable(bar.close_time)}.\n"
        f"Signal reviewed: {'yes' if signal.reviewed else 'no'}.\n"
        f"Signal available now: {'yes' if signal.available_at <= bar.close_time else 'no'}.\n"
        f"Signal expired: {'yes' if signal.expires_at is not None and bar.close_time >= signal.expires_at else 'no'}.\n"
        f"Signal direction: {signal.side}.\n"
        f"Entry condition: {signal.trigger}.\n"
        f"Entry level: {signal.level if signal.level is not None else 'missing'}.\n"
        f"Protective stop: {signal.stop if signal.stop is not None else 'missing'}.\n"
        f"Completed five-minute candle close: {bar.close}.\n"
        "Request: choose buy, sell or hold under the desk rules."
    )
    return {
        "function": FUNCTION,
        "context": {
            "desk": desk,
            "market_context": f"Instrument: {bar.asset}. Synthetic rule test at {jsonable(bar.close_time)}. No future market data.",
        },
        "input": facts,
    }


def cases(experiment: str):
    base = make_signal()
    if experiment in {"original", "all"}:
        for close in [101, 99]:
            bar = make_bar(close)
            yield "original", "trigger_met" if close > 100 else "trigger_not_met", "buy" if close > 100 else "hold", JeffClient._payload(base, bar)["calls"][0]
    if experiment in {"concise", "all"}:
        short = replace(
            base, side="short", trigger="close_below", stop=105, target=90,
            evidence=(Evidence("segment-1", "Sell only after a five-minute close below 100."),),
        )
        fixed = [
            ("long_met", base, 101, "buy"),
            ("long_not_met", base, 99, "hold"),
            ("long_exact_threshold", base, 100, "hold"),
            ("short_met", short, 99, "sell"),
            ("short_not_met", short, 101, "hold"),
            ("missing_stop", replace(base, stop=None), 101, "hold"),
        ]
        for name, signal, close, expected in fixed:
            yield "concise", name, expected, concise_call(signal, make_bar(close))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment", choices=["original", "concise", "all"], default="all")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        import torch
        import jeff
    except ImportError as error:
        parser.error(f"Install the separate Jeff environment from docs/JEFF_SETUP.md: {error}")
    torch.set_num_threads(4)
    started = time.monotonic()
    print("Loading actual Jeff v1.4 weights on CPU", flush=True)
    client = jeff.Jeff.local(["trading-desk"], backend="torch")
    loaded = time.monotonic()
    print(f"Model loaded in {loaded-started:.3f}s", flush=True)
    results = []
    for representation, case, expected, call in cases(args.experiment):
        function = client.function(call["function"], context=call["context"])
        before = time.monotonic()
        answer = function(call["input"])
        result = {
            "representation": representation, "case": case, "expected": expected,
            "elapsed_ms": (time.monotonic()-before)*1000,
            "decision": asdict(answer),
            "matches_expected_label": answer.value == expected,
            "accepted_expected_label": answer.value == expected and not answer.abstained,
            "request": call,
        }
        results.append(result)
        print(json.dumps({key: value for key, value in result.items() if key != "request"}), flush=True)
    payload = {
        "source_commit": CONTRACT_COMMIT,
        "base_version": BASE_VERSION,
        "adapter_version": ADAPTER_VERSION,
        "python": sys.version.split()[0],
        "torch": torch.__version__,
        "cuda_available": torch.cuda.is_available(),
        "threads": torch.get_num_threads(),
        "load_seconds": loaded-started,
        "experiment": args.experiment,
        "results": results,
        "scope": "Actual model weights through official in-process SDK; not the HTTP adapter",
        "limitations": [
            "Synthetic predetermined cases only; no estimate of general accuracy.",
            "No trades, market returns or profitability were tested.",
            "The concise representation is experimental, not the production payload.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

