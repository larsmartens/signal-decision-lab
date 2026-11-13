"""Causal directional-event research, separate from source-stated trade replay.

Holding periods, sizing, price confirmation and costs are researcher-authored rules.
An extracted direction is not a fully specified trading instruction or a calibrated
forecast. This module never calls a model, downloads data, or submits an order.
"""
from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from typing import Any

from .models import Bar, jsonable, positive, utc


HOUR = timedelta(hours=1)


@dataclass(frozen=True)
class ResearchConfig:
    asset: str = "BTCUSDT"
    holding_hours: int = 24
    initial_equity: float = 10_000.0
    fee_bps: float = 10.0
    slippage_bps: float = 5.0
    max_signal_age_hours: float = 24.0
    direction_mode: str = "long_short"
    confirmation: str = "none"
    breakout_lookback_hours: int = 24
    confirmation_window_hours: float = 24.0
    exposure_fraction: float = 1.0
    min_strength: float = 0.0
    sample_start: datetime | str | None = None
    sample_end: datetime | str | None = None

    def __post_init__(self) -> None:
        if not self.asset or self.direction_mode not in {"long_short", "long_only"}:
            raise ValueError("Require an asset and direction_mode long_short or long_only")
        if self.confirmation not in {"none", "breakout"}:
            raise ValueError("confirmation must be none or breakout")
        for key in ("holding_hours", "breakout_lookback_hours"):
            if type(getattr(self, key)) is not int or getattr(self, key) <= 0:
                raise ValueError(f"{key} must be a positive integer")
        for key in ("initial_equity", "max_signal_age_hours", "confirmation_window_hours", "exposure_fraction"):
            positive(getattr(self, key), key)
        for key in ("fee_bps", "slippage_bps", "min_strength"):
            positive(getattr(self, key), key, zero=True)
        if self.exposure_fraction > 1 or self.min_strength > 1:
            raise ValueError("exposure_fraction and min_strength must not exceed one")
        if self.fee_bps >= 10_000 or self.slippage_bps >= 10_000:
            raise ValueError("Fees and slippage must each be below 10,000 basis points")
        for key in ("sample_start", "sample_end"):
            value = getattr(self, key)
            if value is not None:
                value = utc(value)
                if value.minute or value.second or value.microsecond:
                    raise ValueError("Sample boundaries must be UTC hour boundaries")
                object.__setattr__(self, key, value)
        if self.sample_start is not None and self.sample_end is not None:
            if utc(self.sample_start) >= utc(self.sample_end):
                raise ValueError("sample_start must precede sample_end")


@dataclass(frozen=True)
class _Event:
    video_id: str
    available_at: datetime
    direction: str
    strength: float
    variant: str
    asset: str
    metadata: dict

    @property
    def id(self) -> str:
        return f"{self.variant}:{self.video_id}"


@dataclass
class _Position:
    event: _Event
    entry_time: datetime
    raw_entry: float
    entry_price: float
    quantity: float
    entry_fee: float
    exit_at: datetime | None

    @property
    def sign(self) -> int:
        return 1 if self.event.direction == "long" else -1

    def pnl(self, price: float) -> float:
        return self.sign * (price - self.entry_price) * self.quantity


def _parse_events(events: list[dict], config: ResearchConfig) -> list[_Event]:
    result = []
    for item in events:
        if not isinstance(item, dict):
            raise ValueError("Research events must be dictionaries")
        required = {"video_id", "available_at", "direction", "strength", "variant"}
        if not required <= item.keys():
            raise ValueError(f"Research event lacks fields: {sorted(required - item.keys())}")
        if any(not isinstance(item[key], str) or not item[key].strip() for key in ("video_id", "variant")):
            raise ValueError("video_id and variant must be nonempty strings")
        if item["direction"] not in {"long", "short", "flat"}:
            raise ValueError("Research direction must be long, short, or flat")
        positive(item["strength"], "strength", zero=True)
        if item["strength"] > 1:
            raise ValueError("Research strength must be in [0,1]; it is not a probability")
        asset = item.get("asset", config.asset)
        if not isinstance(asset, str) or not asset:
            raise ValueError("Research asset must be a nonempty string")
        metadata = {key: value for key, value in item.items() if key not in required | {"asset"}}
        result.append(_Event(item["video_id"], utc(item["available_at"]), item["direction"],
                             item["strength"], item["variant"], asset, metadata))
    if len({event.id for event in result}) != len(result):
        raise ValueError("Duplicate video_id within a variant would allow repeated source trades")
    return sorted(result, key=lambda event: (event.available_at, event.video_id, event.variant))


def _window(bars: list[Bar], config: ResearchConfig) -> tuple[datetime, datetime, list[Bar], dict]:
    if not bars:
        raise ValueError("Research backtest needs completed price bars")
    if any(bar.asset != config.asset for bar in bars):
        raise ValueError("All market bars must match the configured asset")
    for bar in bars:
        if bar.close_time - bar.open_time != HOUR:
            raise ValueError("Research requires exactly one-hour completed bars")
        if bar.open_time.minute or bar.open_time.second or bar.open_time.microsecond:
            raise ValueError("Research bars must align to UTC hour boundaries")
    if any(current.open_time < previous.close_time for previous, current in zip(bars, bars[1:])):
        raise ValueError("Market bars must be chronological, unique and non-overlapping")
    start = utc(config.sample_start) if config.sample_start is not None else bars[0].open_time
    end = utc(config.sample_end) if config.sample_end is not None else bars[-1].close_time
    if start >= end or start < bars[0].open_time or end > bars[-1].close_time:
        raise ValueError("Sample window must lie within actual market coverage")
    sample = [bar for bar in bars if start <= bar.open_time and bar.close_time <= end]
    if not sample or sample[0].open_time != start or sample[-1].close_time != end:
        raise ValueError("Sample endpoints must have observed bars; never silently shorten a window")
    gaps: list[dict[str, Any]] = [
        {"start": previous.close_time, "end": current.open_time,
         "missing_bars": int((current.open_time - previous.close_time) / HOUR)}
        for previous, current in zip(sample, sample[1:]) if previous.close_time != current.open_time]
    window = {"start": start, "end": end, "end_exclusive": end,
              "first_open": sample[0].open_time, "last_close": sample[-1].close_time,
              "bar_count": len(sample), "expected_bars": int((end - start) / HOUR),
              "missing_bars": sum(gap["missing_bars"] for gap in gaps), "gaps": gaps,
              "asset": config.asset, "interval_hours": 1}
    return start, end, sample, window


def _next_open(available_at: datetime) -> datetime:
    # Strictly after availability, including when publication lands on an hour.
    return available_at.replace(minute=0, second=0, microsecond=0) + HOUR


def _contiguous(history: list[Bar], ending_at: datetime) -> bool:
    return bool(history) and history[-1].close_time == ending_at and all(
        previous.close_time == current.open_time for previous, current in zip(history, history[1:]))


def _simulate(events: list[_Event], bars: list[Bar], config: ResearchConfig,
              *, passive: bool = False) -> dict:
    start, end, sample, window = _window(bars, config)
    fee, slip = config.fee_bps / 10_000, config.slippage_bps / 10_000
    cash = peak = config.initial_equity
    max_drawdown = total_fees = total_slippage = exposure_hours = 0.0
    position: _Position | None = None
    pending: _Event | None = None
    audit: list[dict] = []
    trades: list[dict] = []
    equity: list[dict] = [{"time": start, "equity": cash, "unrealized_pnl": 0.0, "position": None}]
    drawdown: list[dict] = [{"time": start, "drawdown_pct": 0.0}]
    by_video: dict[str, dict[str, Any]] = {
        event.id: {"event_id": event.id, "video_id": event.video_id, "variant": event.variant,
                   "available_at": event.available_at, "direction": event.direction, "strength": event.strength,
                   "status": "unprocessed", "reason": None, "entries": 0, "completed_trades": 0,
                   "realized_net_pnl": 0.0, "unrealized_net_pnl": 0.0, "contribution_net_pnl": 0.0,
                   "metadata": event.metadata} for event in events}
    active_events = []
    open_times = [bar.open_time for bar in bars]
    observed_closes = {bar.close_time for bar in bars}

    def record(event: _Event, at: datetime, kind: str, reason: str, **extra: object) -> None:
        audit.append({"time": at, "type": kind, "event_id": event.id, "video_id": event.video_id,
                      "variant": event.variant, "direction": event.direction, "reason": reason,
                      "reasons": [reason], **extra})
        row = by_video[event.id]
        if kind in {"rejected", "abstained", "unfilled"}:
            row["status"], row["reason"] = kind, reason

    for event in events:
        if event.available_at < start or event.available_at >= end:
            record(event, max(start, min(end, event.available_at)), "rejected", "outside_sample_window")
        elif event.asset != config.asset:
            record(event, event.available_at, "rejected", "asset_mismatch")
        elif event.direction == "flat":
            record(event, event.available_at, "abstained", "flat_signal")
        elif event.strength < config.min_strength:
            record(event, event.available_at, "abstained", "below_strength_threshold")
        elif event.direction == "short" and config.direction_mode == "long_only":
            record(event, event.available_at, "abstained", "short_disabled_cash")
        else:
            active_events.append(event)

    def enter(event: _Event, bar: Bar, reason: str) -> None:
        nonlocal position, cash, total_fees, total_slippage
        if cash <= 0:
            record(event, bar.open_time, "rejected", "no_equity")
            return
        sign = 1 if event.direction == "long" else -1
        fill = bar.open * (1 + sign * slip)
        quantity = cash * config.exposure_fraction / (fill * (1 + fee))
        entry_fee = fill * quantity * fee
        total_fees += entry_fee
        total_slippage += abs(fill - bar.open) * quantity
        cash -= entry_fee
        position = _Position(event, bar.open_time, bar.open, fill, quantity, entry_fee,
                             None if passive else bar.open_time + config.holding_hours * HOUR)
        by_video[event.id]["entries"] += 1
        by_video[event.id]["status"] = "open"
        record(event, bar.open_time, "entry", reason, raw_price=bar.open, price=fill,
               quantity=quantity, notional=fill * quantity, fee=entry_fee,
               scheduled_exit=position.exit_at, available_at=event.available_at)

    def close(bar: Bar, reason: str) -> None:
        nonlocal position, cash, total_fees, total_slippage
        assert position is not None
        fill = bar.open * (1 - position.sign * slip)
        exit_fee = fill * position.quantity * fee
        exit_slippage = abs(fill - bar.open) * position.quantity
        entry_slippage = abs(position.entry_price - position.raw_entry) * position.quantity
        gross = position.pnl(fill)
        net = gross - position.entry_fee - exit_fee
        cash += gross - exit_fee
        total_fees += exit_fee
        total_slippage += exit_slippage
        trades.append({"event_id": position.event.id, "video_id": position.event.video_id,
                       "variant": position.event.variant, "asset": config.asset,
                       "direction": position.event.direction, "side": position.event.direction,
                       "available_at": position.event.available_at, "strength": position.event.strength,
                       "entry_time": position.entry_time, "exit_time": bar.open_time,
                       "exit_time_basis": "observed_bar_open", "scheduled_exit": position.exit_at,
                       "entry_price": position.entry_price, "exit_price": fill,
                       "raw_entry_price": position.raw_entry, "raw_exit_price": bar.open,
                       "quantity": position.quantity, "entry_fee": position.entry_fee,
                       "exit_fee": exit_fee, "fees": position.entry_fee + exit_fee,
                       "slippage_cost": entry_slippage + exit_slippage,
                       "gross_pnl": gross, "net_pnl": net,
                       "net_return_pct": net / (position.entry_price * position.quantity + position.entry_fee) * 100,
                       "holding_hours": (bar.open_time - position.entry_time) / HOUR,
                       "exit_reason": reason})
        row = by_video[position.event.id]
        row["completed_trades"] += 1
        row["realized_net_pnl"] += net
        row["contribution_net_pnl"] += net
        row["status"], row["reason"] = "completed", reason
        record(position.event, bar.open_time, "exit", reason, price=fill, net_pnl=net, fee=exit_fee)
        position = None

    cursor = 0
    previous: Bar | None = None
    for bar in sample:
        if previous is not None and previous.close_time < bar.open_time:
            if position is not None:
                exposure_hours += (bar.open_time - previous.close_time) / HOUR
                if not passive:
                    close(bar, "data_gap_first_observed_open")
            if pending is not None:
                record(pending, bar.open_time, "rejected", "missing_confirmation_bar")
                pending = None
        if position is not None and position.exit_at is not None and bar.open_time >= position.exit_at:
            close(bar, "fixed_holding_period")
        if pending is not None:
            expiry = pending.available_at + timedelta(hours=min(
                config.max_signal_age_hours, config.confirmation_window_hours))
            if bar.open_time >= expiry:
                record(pending, bar.open_time, "abstained", "confirmation_window_expired")
                pending = None

        while cursor < len(active_events):
            event = active_events[cursor]
            expected = start if passive else _next_open(event.available_at)
            if expected > bar.open_time:
                break
            cursor += 1
            if expected != bar.open_time:
                record(event, bar.open_time, "rejected", "missing_entry_bar")
            elif not passive and bar.open_time not in observed_closes:
                record(event, bar.open_time, "rejected", "missing_availability_bar")
            elif bar.open_time >= event.available_at + timedelta(hours=config.max_signal_age_hours):
                record(event, bar.open_time, "abstained", "stale_signal")
            elif config.confirmation == "breakout" and bar.open_time >= event.available_at + timedelta(
                    hours=config.confirmation_window_hours):
                record(event, bar.open_time, "abstained", "confirmation_window_expired")
            elif position is not None or pending is not None:
                record(event, bar.open_time, "rejected", "overlapping_event")
            elif config.confirmation == "none" or passive:
                enter(event, bar, "sample_start_buy_and_hold" if passive else "next_open_after_availability")
            else:
                pending = event
                by_video[event.id]["status"] = "pending"
                record(event, bar.open_time, "pending", "awaiting_price_breakout")

        if pending is not None:
            index = bisect_right(open_times, bar.open_time - HOUR)
            needed = config.breakout_lookback_hours + 1
            history = bars[max(0, index - needed):index]
            if len(history) == needed and _contiguous(history, bar.open_time):
                completed, prior = history[-1], history[:-1]
                threshold = (max(item.high for item in prior) if pending.direction == "long"
                             else min(item.low for item in prior))
                triggered = (completed.close > threshold if pending.direction == "long"
                             else completed.close < threshold)
                if completed.close_time > pending.available_at and triggered:
                    record(pending, bar.open_time, "confirmed", "completed_close_breakout",
                           decision_time=completed.close_time, confirmation_close=completed.close,
                           threshold=threshold, confirmation_bar_open=completed.open_time)
                    enter(pending, bar, "next_contiguous_open_after_confirmation")
                    pending = None

        marked = cash + (position.pnl(bar.close) if position is not None else 0)
        if position is not None:
            exposure_hours += (bar.close_time - bar.open_time) / HOUR
        peak = max(peak, marked)
        dd = (peak - marked) / peak
        max_drawdown = max(max_drawdown, dd)
        equity.append({"time": bar.close_time, "equity": marked,
                       "unrealized_pnl": position.pnl(bar.close) if position else 0.0,
                       "position": position.event.direction if position else None})
        drawdown.append({"time": bar.close_time, "drawdown_pct": dd * 100})
        previous = bar

    for event in active_events[cursor:]:
        record(event, end, "unfilled", "no_entry_open_before_sample_end")
    if pending is not None:
        record(pending, end, "unfilled", "confirmation_unfilled_at_sample_end")
    open_position = None
    if position is not None:
        contribution = position.pnl(sample[-1].close) - position.entry_fee
        by_video[position.event.id]["unrealized_net_pnl"] = contribution
        by_video[position.event.id]["contribution_net_pnl"] += contribution
        open_position = {"event_id": position.event.id, "video_id": position.event.video_id,
                         "variant": position.event.variant, "asset": config.asset,
                         "direction": position.event.direction, "entry_time": position.entry_time,
                         "entry_price": position.entry_price, "raw_entry_price": position.raw_entry,
                         "quantity": position.quantity, "entry_fee": position.entry_fee,
                         "unrealized_pnl": position.pnl(sample[-1].close),
                         "contribution_net_pnl": contribution, "last_price": sample[-1].close,
                         "marked_at": end, "scheduled_exit": position.exit_at,
                         "exit_fees_included": False}
    final_equity = equity[-1]["equity"]
    wins = sum(trade["net_pnl"] > 0 for trade in trades)
    losses = sum(trade["net_pnl"] < 0 for trade in trades)
    gross_wins = sum(max(0, trade["net_pnl"]) for trade in trades)
    gross_losses = -sum(min(0, trade["net_pnl"]) for trade in trades)
    duration_hours = (end - start) / HOUR
    audit.sort(key=lambda item: item["time"])  # Stable ordering retains entry/exit causality at shared boundaries.
    return {"mode": "directional-event-research", "config": config, "window": window,
            "summary": {"initial_equity": config.initial_equity, "final_equity": final_equity,
                        "net_pnl": final_equity - config.initial_equity,
                        "return_pct": (final_equity / config.initial_equity - 1) * 100,
                        "max_drawdown_pct": max_drawdown * 100, "entries": sum(row["entries"] for row in by_video.values()),
                        "completed_trades": len(trades), "wins": wins, "losses": losses,
                        "breakeven_trades": len(trades) - wins - losses,
                        "win_rate_pct": wins / len(trades) * 100 if trades else None,
                        "profit_factor": gross_wins / gross_losses if gross_losses else None,
                        "total_fees": total_fees, "total_slippage": total_slippage,
                        "exposure_hours": exposure_hours, "time_in_market_pct": exposure_hours / duration_hours * 100,
                        "exposure_fraction": config.exposure_fraction,
                        "time_weighted_allocated_capital_pct": config.exposure_fraction * exposure_hours / duration_hours * 100,
                        "event_count": len(events),
                        "rejected_events": sum(row["status"] == "rejected" for row in by_video.values()),
                        "abstained_events": sum(row["status"] == "abstained" for row in by_video.values()),
                        "overlap_events": sum(row["reason"] == "overlapping_event" for row in by_video.values()),
                        "unfilled_events": sum(row["status"] == "unfilled" for row in by_video.values()),
                        "open_positions": int(position is not None)},
            "events": audit, "trades": trades, "equity": equity, "drawdown": drawdown,
            "open_position": open_position, "per_video": list(by_video.values())}


def _momentum_events(events: list[_Event], bars: list[Bar]) -> list[_Event]:
    close_times = [bar.close_time for bar in bars]
    result = []
    for event in events:
        index = bisect_right(close_times, event.available_at)
        history = bars[max(0, index - 24):index]
        direction, reason = "flat", "missing_contiguous_24h_price_history"
        if len(history) == 24 and _contiguous(history, history[-1].close_time):
            # A stale completed candle after a data gap cannot define a current signal.
            if event.available_at - history[-1].close_time < HOUR:
                change = history[-1].close / history[0].open - 1
                direction = "long" if change > 0 else "short" if change < 0 else "flat"
                reason = "last_24_completed_hour_return"
        result.append(_Event(event.video_id, event.available_at, direction, 1.0,
                             "price_only_momentum", event.asset,
                             {"source_variant": event.variant, "benchmark_reason": reason}))
    return result


def run_research_backtest(events: list[dict], bars: list[Bar], config: ResearchConfig = ResearchConfig()) -> dict:
    """Run a frozen event policy and two same-window benchmarks, returning JSON data.

    Events require video_id, available_at, direction, strength and variant. Asset
    defaults to config.asset; extra metadata is retained in per_video. A run may
    contain only one extraction variant, so identical videos cannot be double-used.
    """
    parsed = _parse_events(events, config)
    if len({event.variant for event in parsed}) > 1:
        raise ValueError("Run one extraction variant at a time")
    result = _simulate(parsed, bars, config)
    start = result["window"]["start"]
    passive_event = _Event("buy-and-hold", start, "long", 1.0, "buy_and_hold", config.asset, {})
    passive_config = replace(config, confirmation="none", min_strength=0.0)
    passive = _simulate([passive_event], bars, passive_config, passive=True)
    momentum_config = replace(config, confirmation="none", min_strength=0.0)
    momentum = _simulate(_momentum_events(parsed, bars), bars, momentum_config)
    passive["benchmark_rule"] = "Buy at sample's first observed open, retain position, mark at last completed close."
    momentum["benchmark_rule"] = (
        "At the identical video availability clocks, use the sign of the last 24 fully completed contiguous hourly "
        "candles' return. Use the same holding period, direction mode and costs; no source direction or price-confirmation gate.")
    result["schema_version"] = 1
    result["benchmarks"] = {"buy_and_hold": passive, "price_only_momentum": momentum}
    result["assumptions"] = [
        "Retrospective directional-event research; reconstructed availability is an assumption, not an archived historical observation.",
        "Holding period, sizing and optional breakout are researcher-authored; no stop or target is attributed to the source.",
        "Source strength is a heuristic ranking, not a calibrated probability; it does not determine position size.",
        "One asset, one position and at most one pending event; ties use availability, video_id, variant in that order.",
        "Entry uses the first UTC-hour open strictly after availability; a missing required open rejects the event.",
        "Breakout uses a completed post-availability close beyond the preceding lookback highs/lows, then the contiguous next open.",
        "Fixed holds exit at an observed open; a gap in a held series exits at the first subsequent observed open and records the gap.",
        "Both executed legs incur fees and adverse proportional slippage; initial notional plus its fee never exceeds allocated equity.",
        "Long/short mode is an unlevered synthetic directional proxy on spot prices; short borrow, funding and feasibility are omitted.",
        "Long-only mode holds cash for short events; cash earns no interest. There is no leverage or compounding while a position is open.",
        "Equity and drawdown use completed hourly closes; losses are retained and an insolvent account cannot open another trade.",
        "An end-of-window position stays open at the observed last close; no fictitious liquidation or unincurred exit costs are charged.",
        "Each partition starts in cash. Earlier market bars may warm up causal indicators; pre-window source events cannot carry into it.",
        "Price-only momentum uses the same video clocks, including source-flat clocks, so it isolates the effect of direction selection.",
    ]
    return jsonable(result)
