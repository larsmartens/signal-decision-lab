"""Decision-task calibration; these numbers never measure trading profitability."""
from __future__ import annotations

import math
from .models import utc


def calibration_report(rows: list[dict], bins: int = 10) -> dict:
    if not rows or type(bins) is not int or not 1 <= bins <= 100:
        raise ValueError("Need non-empty labeled predictions and bins in [1,100]")
    scores, brier, accepted, correct = [], 0.0, 0, 0
    for row in rows:
        if not isinstance(row, dict) or not {"probabilities", "label", "observed_at", "predicted_at"} <= set(row):
            raise ValueError("Every row needs probabilities, label, predicted_at and observed_at")
        p = row["probabilities"]
        label = row["label"]
        if not isinstance(p, dict) or set(p) != {"buy", "sell", "hold"} or label not in p:
            raise ValueError("Labels and probabilities must use buy, sell, hold")
        if any(type(x) not in {float, int} or not math.isfinite(x) or not 0 <= x <= 1 for x in p.values()) or abs(sum(p.values()) - 1) > 1e-6:
            raise ValueError("Invalid probability distribution")
        if utc(row["observed_at"]) < utc(row["predicted_at"]):
            raise ValueError("Outcome labels cannot be observed before prediction")
        if type(row.get("abstained", False)) is not bool:
            raise ValueError("abstained must be boolean")
        # Fixed order makes ties invariant to JSON object key order; hold wins.
        chosen = max(("hold", "buy", "sell"), key=lambda key: p[key])
        is_correct = chosen == label
        correct += is_correct
        scores.append((p[chosen], is_correct))
        brier += sum((prob - int(key == label)) ** 2 for key, prob in p.items())
        accepted += not row.get("abstained", False)
    buckets = []
    ece = 0.0
    for i in range(bins):
        items = [(c, a) for c, a in scores if min(int(c * bins), bins - 1) == i]
        if not items:
            continue
        confidence = sum(c for c, _ in items) / len(items)
        accuracy = sum(a for _, a in items) / len(items)
        ece += len(items) / len(rows) * abs(confidence - accuracy)
        buckets.append({"lower": i / bins, "upper": (i+1) / bins, "count": len(items), "confidence": confidence, "accuracy": accuracy})
    return {"task": "rule_decision_classification", "rows": len(rows), "accuracy": correct / len(rows), "brier_multiclass_sum": brier / len(rows), "ece": ece, "coverage": accepted / len(rows), "buckets": buckets, "limitation": "Calibration on these labeled decisions only; no estimate of trade win probability or P&L."}
