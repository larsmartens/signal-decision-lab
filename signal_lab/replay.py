"""Chronological single-position paper simulator with explicit fill assumptions."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import math
import re
from typing import Callable

from .engine import Policy, deadline, decide
from .models import Bar, Signal, jsonable


Judge = Callable[[Signal, Bar], dict]
_DECISION_FIELDS = ("value", "confidence", "probabilities", "abstained", "calibrated")
_JEV_FIELDS = ("provider", "model", "provider_confidence", "probability_source", "calibration_source")


def _jev_experiment(answer: dict) -> bool:
    """Recognize an explicitly selected Jev experiment without claiming calibration."""
    score = answer.get("provider_confidence")
    model = answer.get("model")
    return (
        answer.get("provider") == "typesafe"
        and answer.get("probability_source") == "jev_model"
        and answer.get("calibration_source") == "provider_claim_not_locally_validated"
        and answer.get("calibrated") is False
        and isinstance(model, str)
        and re.fullmatch(r"jev-[0-9]+\.[0-9]+\.[0-9]+", model) is not None
        and not isinstance(score, bool)
        and isinstance(score, (int, float))
        and 0 <= score <= 1
        and math.isfinite(score)
    )


@dataclass
class _Position:
    signal: Signal
    entry_time: datetime
    entry_price: float
    quantity: float
    entry_fee: float

    @property
    def sign(self) -> int:
        return 1 if self.signal.side == "long" else -1

    def mark(self, price: float) -> float:
        return self.sign * (price - self.entry_price) * self.quantity


def _model_check(answer: object, signal: Signal, policy: Policy) -> tuple[bool, str]:
    if not isinstance(answer, dict):
        return False, "model_invalid_response"
    if type(answer.get("abstained")) is not bool or type(answer.get("calibrated")) is not bool:
        return False, "model_invalid_response"
    probs = answer.get("probabilities")
    if not isinstance(probs, dict) or set(probs) != {"buy", "sell", "hold"}:
        return False, "model_invalid_probabilities"
    for p in probs.values():
        if isinstance(p, bool) or not isinstance(p, (float, int)) or not math.isfinite(p) or not 0 <= p <= 1:
            return False, "model_invalid_probabilities"
    if abs(sum(probs.values()) - 1) > 1e-6:
        return False, "model_invalid_probabilities"
    value, confidence = answer.get("value"), answer.get("confidence")
    if value not in probs or isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        return False, "model_invalid_response"
    if answer.get("probability_source") == "fail_closed_policy":
        if value != "hold" or confidence != 0 or not answer["abstained"] or answer["calibrated"] or probs != {"buy": 0.0, "sell": 0.0, "hold": 1.0}:
            return False, "model_invalid_response"
        return False, "model_policy_abstention"
    if not math.isfinite(confidence) or abs(confidence - probs[value]) > 1e-6:
        return False, "model_invalid_response"
    if probs[value] < max(probs.values()) - 1e-9:
        return False, "model_invalid_response"
    if answer["abstained"]:
        return False, "model_abstained"
    if not answer["calibrated"] and not _jev_experiment(answer):
        return False, "model_uncalibrated"
    if confidence < policy.min_model_confidence:
        return False, "model_low_confidence"
    expected = "buy" if signal.side == "long" else "sell"
    return (True, "model_agreed") if value == expected else (False, "model_disagreement")


def _rejected_jev_evidence(answer: object, signal: Signal, policy: Policy) -> dict | None:
    """Keep a valid rejected prediction separate from the effective policy hold."""
    if not isinstance(answer, dict) or not _jev_experiment(answer):
        return None
    try:
        _, reason = _model_check(answer, signal, policy)
    except (ValueError, TypeError, OverflowError):
        return None
    if reason not in {"model_agreed", "model_disagreement", "model_low_confidence"}:
        return None
    return {key: answer[key] for key in (*_DECISION_FIELDS, *_JEV_FIELDS)}


def _validate_inputs(signals: list[Signal], bars: list[Bar]) -> None:
    if not bars:
        raise ValueError("Replay needs at least one completed price bar")
    if len({signal.id for signal in signals}) != len(signals):
        raise ValueError("Duplicate signal IDs would allow duplicate trades")
    if len({bar.asset for bar in bars}) != 1:
        raise ValueError("Replay supports one price series/asset per run")
    for previous, current in zip(bars, bars[1:]):
        if current.open_time < previous.close_time:
            raise ValueError("Bars must be strictly chronological and non-overlapping")


def _exit_price(position: _Position, bar: Bar) -> tuple[float, str, datetime, str] | None:
    signal, sign = position.signal, position.sign
    assert signal.stop is not None and signal.target is not None
    if sign * (bar.open - signal.stop) <= 0:
        return bar.open, "stop_gap", bar.open_time, "bar_open"
    expiry = deadline(signal)
    if expiry is not None and bar.open_time >= expiry:
        return bar.open, "expired", bar.open_time, "bar_open"
    if sign * (bar.open - signal.target) >= 0:
        # The open establishes target-first order, so this is not an ambiguous
        # intrabar collision. Do not award price improvement beyond the target.
        return signal.target, "target_gap", bar.open_time, "bar_open"
    stop_hit = bar.low <= signal.stop if sign == 1 else bar.high >= signal.stop
    target_hit = bar.high >= signal.target if sign == 1 else bar.low <= signal.target
    if stop_hit:
        return signal.stop, "stop_before_target" if target_hit else "stop", bar.close_time, "bar_close_bound"
    if target_hit:
        return signal.target, "target", bar.close_time, "bar_close_bound"
    return None


def run_replay(signals: list[Signal], bars: list[Bar], policy: Policy = Policy(),
               judge: Judge | None = None) -> dict:
    """Replay known-at-time signals; an optional model judge may only veto entries.

    The callback receives one frozen completed bar and one frozen signal. It receives
    neither the historical container nor future prices. External callback behavior is
    the caller's responsibility; this function does not claim remote model validation.
    """
    _validate_inputs(signals, bars)
    ordered = sorted(signals, key=lambda s: (s.available_at, s.id))
    cash = peak = policy.initial_equity
    max_drawdown = total_fees = 0.0
    fee, slip = policy.fee_bps / 10_000, policy.slippage_bps / 10_000
    position: _Position | None = None
    pending: tuple[Signal, datetime] | None = None
    consumed: set[str] = set()
    rejected: set[str] = set()
    waiting: dict[str, tuple[str, ...]] = {}
    halted = False
    risk_exit_pending = False
    model_calls = entries = 0
    events: list[dict] = []
    trades: list[dict] = []
    equity: list[dict] = [{"time": bars[0].open_time, "equity": cash, "unrealized_pnl": 0.0}]

    def event(time: datetime, kind: str, signal: Signal | None, *reasons: str, **extra: object) -> None:
        events.append({"time": time, "type": kind, "signal_id": signal.id if signal else None,
                       "reasons": list(reasons), **extra})

    def close(raw_price: float, reason: str, at: datetime, time_basis: str) -> None:
        nonlocal position, cash, total_fees
        assert position is not None
        fill = raw_price * (1 - position.sign * slip)
        exit_fee = fill * position.quantity * fee
        gross = position.mark(fill)
        cash += gross - exit_fee
        total_fees += exit_fee
        net = gross - position.entry_fee - exit_fee
        trades.append({"signal_id": position.signal.id, "asset": position.signal.asset,
                       "side": position.signal.side, "entry_time": position.entry_time,
                       "exit_time": at, "exit_time_basis": time_basis,
                       "entry_price": position.entry_price, "exit_price": fill,
                       "quantity": position.quantity, "entry_fee": position.entry_fee,
                       "exit_fee": exit_fee, "fees": position.entry_fee + exit_fee,
                       "gross_pnl": gross, "net_pnl": net, "exit_reason": reason})
        event(at, "exit", position.signal, reason, price=fill, quantity=position.quantity, net_pnl=net)
        position = None

    for bar in bars:
        if risk_exit_pending and position is not None:
            # The previous close triggered the halt. The next observed open is
            # the earliest executable price; adverse gaps are part of the loss.
            close(bar.open, "max_drawdown", bar.open_time, "bar_open")
            risk_exit_pending = False
        if pending is not None:
            signal, decision_time = pending
            pending = None
            expiry = deadline(signal)
            reason = None
            if bar.open_time != decision_time:
                reason = "noncontiguous_next_bar"
            elif expiry is None or bar.open_time >= expiry:
                reason = "expired_before_fill"
            elif signal.asset != bar.asset:
                reason = "asset_mismatch"
            if reason:
                rejected.add(signal.id)
                event(bar.open_time, "order_cancelled", signal, reason)
            else:
                sign = 1 if signal.side == "long" else -1
                assert signal.stop is not None and signal.target is not None
                entry = bar.open * (1 + sign * slip)
                stop_fill = signal.stop * (1 - sign * slip)
                target_fill = signal.target * (1 - sign * slip)
                unit_risk = sign * (entry - stop_fill) + fee * (entry + stop_fill)
                unit_reward = sign * (target_fill - entry) - fee * (entry + target_fill)
                if sign * (entry - signal.stop) <= 0 or sign * (signal.target - entry) <= 0:
                    reason = "entry_gap_outside_bracket"
                elif unit_risk <= 0 or unit_reward / unit_risk < policy.min_reward_risk:
                    reason = "fill_reward_risk_too_low"
                elif cash <= 0:
                    reason = "no_equity"
                if reason:
                    rejected.add(signal.id)
                    event(bar.open_time, "order_cancelled", signal, reason)
                else:
                    quantity = min(cash * policy.risk_fraction / unit_risk,
                                   cash * policy.max_exposure_fraction / (entry * (1 + fee)))
                    entry_fee = quantity * entry * fee
                    position = _Position(signal, bar.open_time, entry, quantity, entry_fee)
                    cash -= entry_fee
                    total_fees += entry_fee
                    entries += 1
                    event(bar.open_time, "entry", signal, "next_open", price=entry,
                          quantity=quantity, planned_stop_loss=quantity * unit_risk,
                          notional=entry * quantity, fee=entry_fee)

        if position is not None:
            exit_data = _exit_price(position, bar)
            if exit_data:
                close(*exit_data)

        marked = cash + (position.mark(bar.close) if position else 0.0)
        peak = max(peak, marked)
        drawdown = (peak - marked) / peak
        max_drawdown = max(max_drawdown, drawdown)
        if drawdown >= policy.max_drawdown_fraction and not halted:
            halted = True
            event(bar.close_time, "risk_halt", position.signal if position else None, "max_drawdown")
            if position:
                risk_exit_pending = True
                event(bar.close_time, "risk_exit_queued", position.signal, "next_observed_open")
        equity.append({"time": bar.close_time, "equity": marked,
                       "unrealized_pnl": position.mark(bar.close) if position else 0.0})
        if position is not None or halted:
            continue

        eligible: list[Signal] = []
        for signal in ordered:
            if signal.id in consumed or signal.available_at > bar.close_time:
                continue
            decision = decide(signal, bar, policy=policy)
            if decision.action == "reject":
                consumed.add(signal.id)
                rejected.add(signal.id)
                event(bar.close_time, "signal_rejected", signal, *decision.reasons)
            elif decision.action.startswith("enter_"):
                eligible.append(signal)
            elif waiting.get(signal.id) != decision.reasons:
                waiting[signal.id] = decision.reasons
                event(bar.close_time, "signal_waiting", signal, *decision.reasons)
        if len({signal.side for signal in eligible}) > 1:
            for signal in eligible:
                consumed.add(signal.id)
                rejected.add(signal.id)
                event(bar.close_time, "signal_rejected", signal, "conflicting_directions")
            continue
        if not eligible:
            continue
        signal = eligible[0]
        consumed.add(signal.id)
        if judge is not None:
            model_calls += 1
            try:
                answer = judge(signal, bar)
                accepted, reason = _model_check(answer, signal, policy)
            except Exception:
                answer, accepted, reason = None, False, "model_error"
            detail = {}
            if isinstance(answer, dict) and reason not in {"model_invalid_probabilities", "model_invalid_response"}:
                detail = {key: answer[key] for key in _DECISION_FIELDS}
                if _jev_experiment(answer):
                    for key in _JEV_FIELDS:
                        detail[key] = answer[key]
                if reason == "model_policy_abstention":
                    detail["probability_source"] = "fail_closed_policy"
                    # Preserve a bounded cause code, never raw provider errors.
                    code = answer.get("error_code")
                    if isinstance(code, str) and len(code) <= 64 and all(c.islower() or c == "_" for c in code):
                        detail["error_code"] = code
                    original = _rejected_jev_evidence(answer.get("model_decision"), signal, policy)
                    if original is not None:
                        detail["model_decision"] = original
            event(bar.close_time, "model_judgment", signal, reason, **detail)
            if not accepted:
                rejected.add(signal.id)
                continue
        pending = (signal, bar.close_time)
        event(bar.close_time, "order_queued", signal, "eligible", action=f"enter_{signal.side}")

    if pending is not None:
        event(bars[-1].close_time, "order_unfilled", pending[0], "end_of_data")
    if risk_exit_pending and position is not None:
        event(bars[-1].close_time, "risk_exit_unfilled", position.signal, "end_of_data")
    final_equity = equity[-1]["equity"]
    open_position = None
    if position:
        open_position = {"signal_id": position.signal.id, "asset": position.signal.asset,
                         "side": position.signal.side, "entry_time": position.entry_time,
                         "entry_price": position.entry_price, "quantity": position.quantity,
                         "entry_fee": position.entry_fee,
                         "unrealized_pnl": position.mark(bars[-1].close),
                         "last_price": bars[-1].close, "expires_at": deadline(position.signal)}
    return jsonable({"mode": "paper-replay", "policy": policy,
        "assumptions": [
            "Synthetic scenarios establish behavior, never profitability.",
            "One asset and one position; no exchange connection, leverage, funding or borrow costs.",
            "Signals are eligible at availability; completed-bar decisions fill only at the next contiguous open.",
            "Both legs pay fees and adverse proportional slippage; size includes modeled stop costs.",
            "A stop/target collision assumes the stop first; stop gaps fill at the adverse open.",
            "Intrabar exit_time is the bar-close upper bound, not an observed execution timestamp.",
            "Expiry exits at the first observed bar open at/after deadline; gaps can delay exits.",
            "End-of-data positions remain open and marked at last close; no fictitious liquidation.",
            "Drawdown is measured at completed closes; a halt queues liquidation at the next observed open, including gaps.",
            "The model gate uses the selected action's probability. Calibration on these inputs has not been measured."],
        "summary": {"initial_equity": policy.initial_equity, "final_equity": final_equity,
                    "net_pnl": final_equity - policy.initial_equity,
                    "return_pct": (final_equity / policy.initial_equity - 1) * 100,
                    "max_drawdown_pct": max_drawdown * 100, "completed_trades": len(trades),
                    "entries": entries, "total_fees": total_fees, "model_calls": model_calls,
                    "rejected_signals": len(rejected), "halted": halted},
        "events": events, "trades": trades, "equity": equity, "open_position": open_position})
