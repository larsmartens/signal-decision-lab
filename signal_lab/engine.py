"""Deterministic eligibility rules; model probabilities never override these."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from .models import Bar, Signal, positive


@dataclass(frozen=True)
class Policy:
    risk_fraction: float = 0.0025
    max_exposure_fraction: float = 1.0
    initial_equity: float = 10_000.0
    fee_bps: float = 5.0
    slippage_bps: float = 2.0
    max_drawdown_fraction: float = 0.1
    allow_short: bool = False
    min_reward_risk: float = 1.5
    min_model_confidence: float = 0.8

    def __post_init__(self) -> None:
        for name in ("risk_fraction", "max_exposure_fraction", "max_drawdown_fraction",
                     "min_model_confidence"):
            value = getattr(self, name)
            positive(value, name)
            if value > 1:
                raise ValueError(f"{name} cannot exceed 1")
        positive(self.initial_equity, "initial_equity")
        positive(self.min_reward_risk, "min_reward_risk")
        for name in ("fee_bps", "slippage_bps"):
            value = getattr(self, name)
            positive(value, name, zero=True)
            if value >= 10_000:
                raise ValueError(f"{name} must be below 10000")
        if type(self.allow_short) is not bool:
            raise ValueError("allow_short must be a boolean")


@dataclass(frozen=True)
class Decision:
    signal_id: str
    as_of: datetime
    action: str
    reasons: tuple[str, ...]


def deadline(signal: Signal) -> datetime | None:
    """Both explicit expiry and stated horizon bound the setup/holding window."""
    if signal.expires_at is None or signal.horizon_minutes is None:
        return None
    return min(signal.expires_at,
               signal.available_at + timedelta(minutes=signal.horizon_minutes))


def decide(signal: Signal, bar: Bar, *, policy: Policy = Policy()) -> Decision:
    """Evaluate an available statement using one completed bar, never future bars.

    A close-above/below trigger is a level condition, not a crossover detector.
    A caller must still recheck price, expiry and sizing at the next open.
    """
    def result(action: str, *reasons: str) -> Decision:
        return Decision(signal.id, bar.close_time, action, tuple(reasons))

    if signal.available_at > bar.close_time:
        return result("wait", "not_available")
    problems: list[str] = []
    if signal.asset != bar.asset:
        problems.append("asset_mismatch")
    if not signal.reviewed:
        problems.append("review_required")
    if signal.issues:
        problems.append("extraction_issues")
    if signal.statement_type not in {"conditional", "actionable"}:
        problems.append("not_actionable")
    if signal.side not in {"long", "short"}:
        problems.append("direction_missing")
    if signal.side == "short" and not policy.allow_short:
        problems.append("short_disabled")
    if signal.trigger == "none":
        problems.append("trigger_missing")
    for name in ("level", "stop", "target", "timeframe_minutes", "horizon_minutes", "expires_at"):
        if getattr(signal, name) is None:
            problems.append(f"{name}_missing")
    if signal.timeframe_minutes is not None:
        duration = (bar.close_time - bar.open_time).total_seconds()
        if duration != signal.timeframe_minutes * 60:
            problems.append("timeframe_mismatch")
    expiry = deadline(signal)
    if expiry is not None and bar.close_time >= expiry:
        problems.append("expired")
    if problems:
        return result("reject", *problems)

    # Explicit guards above establish the complete numeric bracket.
    assert signal.level is not None and signal.stop is not None and signal.target is not None
    sign = 1 if signal.side == "long" else -1
    if sign * (signal.level - signal.stop) <= 0 or sign * (signal.target - signal.level) <= 0:
        return result("reject", "invalid_bracket")
    triggered = ((signal.trigger == "close_above" and bar.close > signal.level)
                 or (signal.trigger == "close_below" and bar.close < signal.level))
    if not triggered:
        return result("wait", "trigger_not_met")
    risk = sign * (bar.close - signal.stop)
    reward = sign * (signal.target - bar.close)
    if risk <= 0 or reward <= 0:
        return result("reject", "price_outside_bracket")
    if reward / risk < policy.min_reward_risk:
        return result("reject", "reward_risk_too_low")
    return result(f"enter_{signal.side}", "eligible")
