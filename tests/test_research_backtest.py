"""Behavioral checks use artificial prices; they make no profitability claim."""
from dataclasses import replace
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts.fetch_market_bars import fetch, normalize_row
from signal_lab.models import Bar
from signal_lab.research_backtest import ResearchConfig, run_research_backtest


T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
FREE = ResearchConfig(holding_hours=2, fee_bps=0, slippage_bps=0)


def bar(index, price=100, *, close=None, high=None, low=None):
    close = price if close is None else close
    return Bar("BTCUSDT", T0 + timedelta(hours=index), T0 + timedelta(hours=index + 1),
               price, max(price, close) if high is None else high,
               min(price, close) if low is None else low, close)


def event(video_id="video-1", available_hours=0, direction="long", **extra):
    return {"video_id": video_id, "available_at": T0 + timedelta(hours=available_hours),
            "direction": direction, "strength": .8, "variant": "test", **extra}


def stamps(hours):
    return (T0 + timedelta(hours=hours)).isoformat().replace("+00:00", "Z")


class ResearchBacktestTests(unittest.TestCase):
    def test_availability_exactly_at_open_still_waits_for_next_open(self):
        result = run_research_backtest([event()], [bar(i) for i in range(5)], FREE)
        self.assertEqual(result["trades"][0]["entry_time"], stamps(1))
        self.assertEqual(result["trades"][0]["exit_time"], stamps(3))
        self.assertEqual(result["trades"][0]["holding_hours"], 2)
        self.assertEqual(result["summary"]["time_in_market_pct"], 40)

    def test_mid_hour_availability_cannot_fill_same_bar(self):
        result = run_research_backtest([event(available_hours=.5)], [bar(i) for i in range(5)], FREE)
        self.assertEqual(result["trades"][0]["entry_time"], stamps(1))

    def test_both_executed_legs_pay_fees_and_adverse_slippage(self):
        config = replace(FREE, fee_bps=10, slippage_bps=5)
        result = run_research_backtest([event()], [bar(0), bar(1), bar(2), bar(3, 110)], config)
        trade = result["trades"][0]
        quantity = 10_000 / (100 * 1.0005 * 1.001)
        self.assertAlmostEqual(trade["quantity"], quantity)
        self.assertAlmostEqual(trade["entry_price"], 100 * 1.0005)
        self.assertAlmostEqual(trade["exit_price"], 110 * .9995)
        self.assertAlmostEqual(trade["fees"], quantity * (100 * 1.0005 + 110 * .9995) * .001)
        self.assertAlmostEqual(trade["slippage_cost"], quantity * (100 + 110) * .0005)
        self.assertAlmostEqual(trade["net_pnl"], trade["gross_pnl"] - trade["fees"])
        self.assertAlmostEqual(result["summary"]["final_equity"], 10_000 + trade["net_pnl"])
        self.assertLessEqual(quantity * trade["entry_price"] + trade["entry_fee"], 10_000 + 1e-9)

    def test_stress_costs_reduce_same_trade_outcome(self):
        prices = [bar(0), bar(1), bar(2), bar(3, 110)]
        base = run_research_backtest([event()], prices, replace(FREE, fee_bps=10, slippage_bps=5))
        stress = run_research_backtest([event()], prices, replace(FREE, fee_bps=20, slippage_bps=10))
        self.assertEqual(base["trades"][0]["entry_time"], stress["trades"][0]["entry_time"])
        self.assertLess(stress["summary"]["net_pnl"], base["summary"]["net_pnl"])

    def test_losses_are_kept_and_contributions_reconcile(self):
        result = run_research_backtest([event()], [bar(0), bar(1), bar(2), bar(3, 80)], FREE)
        self.assertEqual(result["summary"]["losses"], 1)
        self.assertEqual(result["summary"]["net_pnl"], -2000)
        self.assertEqual(result["summary"]["max_drawdown_pct"], 20)
        self.assertEqual(sum(row["contribution_net_pnl"] for row in result["per_video"]), -2000)

    def test_profit_factor_is_reproducible_across_python_float_sum_versions(self):
        # Seven small compounding gains and one loss expose the changed float
        # summation in Python 3.12. Sequential addition yields ...3583 instead.
        prices, signals = [], []
        for index in range(8):
            hour = index * 3
            prices.extend((bar(hour), bar(hour + 1), bar(hour + 2, 100.1 if index < 7 else 99.7)))
            signals.append(event(f"video-{index}", available_hours=hour))
        result = run_research_backtest(signals, prices, replace(FREE, holding_hours=1))
        self.assertEqual(result["summary"]["completed_trades"], 8)
        self.assertEqual((result["summary"]["wins"], result["summary"]["losses"]), (7, 1))
        self.assertEqual(result["summary"]["profit_factor"], 2.3240279301535827)

    def test_short_sign_and_long_only_cash_semantics(self):
        prices = [bar(0), bar(1), bar(2), bar(3, 90)]
        short = run_research_backtest([event(direction="short")], prices, FREE)
        cash = run_research_backtest([event(direction="short")], prices, replace(FREE, direction_mode="long_only"))
        self.assertEqual(short["summary"]["net_pnl"], 1000)
        self.assertEqual(cash["summary"]["entries"], 0)
        self.assertEqual(cash["summary"]["net_pnl"], 0)
        self.assertEqual(cash["events"][0]["reason"], "short_disabled_cash")

    def test_short_costs_move_fills_against_the_position(self):
        result = run_research_backtest([event(direction="short")],
                                      [bar(0), bar(1), bar(2), bar(3, 90)],
                                      replace(FREE, fee_bps=10, slippage_bps=5))
        trade = result["trades"][0]
        self.assertLess(trade["entry_price"], 100)
        self.assertGreater(trade["exit_price"], 90)
        self.assertGreater(trade["entry_fee"], 0)
        self.assertGreater(trade["exit_fee"], 0)
        self.assertAlmostEqual(result["summary"]["net_pnl"], trade["net_pnl"])

    def test_window_end_does_not_invent_the_next_open_or_exit_fee(self):
        config = replace(FREE, fee_bps=10)
        result = run_research_backtest([event()], [bar(0), bar(1), bar(2, 80)], config)
        self.assertEqual(result["trades"], [])
        self.assertIsNotNone(result["open_position"])
        self.assertEqual(result["open_position"]["scheduled_exit"], stamps(3))
        self.assertFalse(result["open_position"]["exit_fees_included"])
        self.assertEqual(result["summary"]["total_fees"], result["open_position"]["entry_fee"])
        self.assertAlmostEqual(result["per_video"][0]["contribution_net_pnl"], result["summary"]["net_pnl"])

    def test_last_hour_signal_remains_unfilled(self):
        result = run_research_backtest([event(available_hours=2.5)], [bar(i) for i in range(3)], FREE)
        self.assertEqual(result["summary"]["entries"], 0)
        self.assertEqual(result["summary"]["unfilled_events"], 1)
        self.assertEqual(result["events"][0]["reason"], "no_entry_open_before_sample_end")

    def test_sample_boundaries_and_benchmarks_use_exact_same_horizon(self):
        config = replace(FREE, sample_start=stamps(3), sample_end=stamps(8))
        inputs = [event("before", 2), event("inside", 3), event("after", 8)]
        result = run_research_backtest(inputs, [bar(i) for i in range(12)], config)
        self.assertEqual(result["summary"]["entries"], 1)
        self.assertEqual(result["trades"][0]["video_id"], "inside")
        self.assertEqual(result["summary"]["rejected_events"], 2)
        for run in [result, *result["benchmarks"].values()]:
            self.assertEqual(run["equity"][0]["time"], stamps(3))
            self.assertEqual(run["equity"][-1]["time"], stamps(8))
            self.assertEqual(run["window"]["bar_count"], 5)

    def test_prices_after_sample_end_do_not_change_any_result(self):
        config = replace(FREE, sample_start=stamps(3), sample_end=stamps(8))
        first = [bar(i) for i in range(12)]
        changed = [bar(i, 900 if i >= 8 else 100) for i in range(12)]
        self.assertEqual(run_research_backtest([event(available_hours=3)], first, config),
                         run_research_backtest([event(available_hours=3)], changed, config))

    def test_future_source_event_cannot_change_earlier_trade(self):
        prices = [bar(i) for i in range(8)]
        base = run_research_backtest([event()], prices, FREE)
        extra = run_research_backtest([event(), event("later", 5)], prices, FREE)
        self.assertEqual(base["trades"][0], extra["trades"][0])
        self.assertEqual(base["equity"][:5], extra["equity"][:5])

    def test_overlap_and_same_time_tie_are_deterministic(self):
        inputs = [event("z", direction="short"), event("a"), event("during", 1.5)]
        result = run_research_backtest(inputs, [bar(i) for i in range(5)], FREE)
        self.assertEqual(result["trades"][0]["video_id"], "a")
        self.assertEqual(result["summary"]["entries"], 1)
        self.assertEqual(result["summary"]["overlap_events"], 2)
        self.assertEqual(result, run_research_backtest(list(reversed(inputs)), [bar(i) for i in range(5)], FREE))

    def test_flat_low_strength_and_stale_signals_abstain(self):
        prices = [bar(i) for i in range(4)]
        cases = [(event(direction="flat"), FREE, "flat_signal"),
                 (event(strength=.2), replace(FREE, min_strength=.5), "below_strength_threshold"),
                 (event(), replace(FREE, max_signal_age_hours=.5), "stale_signal")]
        for item, config, reason in cases:
            with self.subTest(reason=reason):
                result = run_research_backtest([item], prices, config)
                self.assertEqual(result["summary"]["entries"], 0)
                self.assertEqual(result["events"][0]["reason"], reason)

    def test_unmatched_asset_cannot_trade_the_supplied_series(self):
        result = run_research_backtest([event(asset="ETHUSDT")], [bar(i) for i in range(4)], FREE)
        self.assertEqual(result["summary"]["entries"], 0)
        self.assertEqual(result["events"][0]["reason"], "asset_mismatch")
        with self.assertRaises(ValueError):
            run_research_backtest([event()], [replace(bar(0), asset="ETHUSDT")], FREE)

    def test_missing_required_entry_open_is_not_chased(self):
        result = run_research_backtest([event(available_hours=.5)], [bar(0), bar(2), bar(3)], FREE)
        self.assertEqual(result["summary"]["entries"], 0)
        self.assertEqual(result["events"][0]["reason"], "missing_entry_bar")
        self.assertEqual(result["window"]["missing_bars"], 1)

    def test_missing_candle_containing_availability_blocks_an_entry(self):
        result = run_research_backtest([event(available_hours=1.5)], [bar(0), bar(2), bar(3)], FREE)
        self.assertEqual(result["summary"]["entries"], 0)
        self.assertEqual(result["events"][0]["reason"], "missing_availability_bar")

    def test_held_position_gap_uses_next_real_open_and_keeps_its_loss(self):
        result = run_research_backtest([event()], [bar(0), bar(1), bar(3, 50), bar(4, 50)],
                                      replace(FREE, holding_hours=24))
        self.assertEqual(result["trades"][0]["exit_time"], stamps(3))
        self.assertEqual(result["trades"][0]["exit_price"], 50)
        self.assertEqual(result["trades"][0]["exit_reason"], "data_gap_first_observed_open")
        self.assertEqual(result["summary"]["net_pnl"], -5000)
        self.assertEqual(result["summary"]["exposure_hours"], 2)
        self.assertEqual(result["benchmarks"]["buy_and_hold"]["trades"], [])
        self.assertEqual(result["benchmarks"]["buy_and_hold"]["summary"]["time_in_market_pct"], 100)

    def test_breakout_reads_completed_prior_candle_and_fills_next_contiguous_open(self):
        prices = [bar(0, high=101), bar(1, high=102), bar(2, close=105),
                  bar(3, 107), bar(4, 110), bar(5, 110)]
        config = replace(FREE, confirmation="breakout", breakout_lookback_hours=2, holding_hours=1)
        result = run_research_backtest([event(available_hours=2.5)], prices, config)
        trade = result["trades"][0]
        self.assertEqual(trade["entry_time"], stamps(3))
        self.assertEqual(trade["entry_price"], 107)
        confirmed = next(row for row in result["events"] if row["type"] == "confirmed")
        self.assertEqual(confirmed["threshold"], 102)
        self.assertEqual(confirmed["confirmation_close"], 105)
        self.assertEqual(confirmed["confirmation_bar_open"], stamps(2))

    def test_breakout_cannot_use_current_hour_close_for_same_open_fill(self):
        prices = [bar(0), bar(1), bar(2), bar(3, close=150), bar(4, 155), bar(5, 155)]
        config = replace(FREE, confirmation="breakout", breakout_lookback_hours=2, holding_hours=1)
        result = run_research_backtest([event(available_hours=2.5)], prices, config)
        self.assertEqual(result["trades"][0]["entry_time"], stamps(4))
        self.assertEqual(result["trades"][0]["entry_price"], 155)

    def test_confirmation_window_can_expire_before_first_open(self):
        config = replace(FREE, confirmation="breakout", confirmation_window_hours=.25)
        result = run_research_backtest([event()], [bar(i) for i in range(4)], config)
        self.assertEqual(result["summary"]["entries"], 0)
        self.assertEqual(result["events"][0]["reason"], "confirmation_window_expired")

    def test_missing_breakout_history_cannot_be_filled_with_future_prices(self):
        config = replace(FREE, confirmation="breakout", breakout_lookback_hours=24)
        result = run_research_backtest([event()], [bar(i, 100 + i) for i in range(5)], config)
        self.assertEqual(result["summary"]["entries"], 0)
        self.assertEqual(result["summary"]["unfilled_events"], 1)

    def test_momentum_uses_same_source_flat_clock_and_only_then_completed_prices(self):
        prices = [bar(i, 100, close=120 if i == 25 else 100) for i in range(31)]
        source = event(available_hours=26.5, direction="flat")
        result = run_research_backtest([source], prices, FREE)
        benchmark = result["benchmarks"]["price_only_momentum"]
        self.assertEqual(result["summary"]["entries"], 0)
        self.assertEqual(benchmark["trades"][0]["direction"], "long")
        self.assertEqual(benchmark["trades"][0]["entry_time"], stamps(27))
        changed = list(prices)
        changed[26] = bar(26, 100, close=10)
        alternate = run_research_backtest([source], changed, FREE)["benchmarks"]["price_only_momentum"]
        self.assertEqual(benchmark["trades"][0], alternate["trades"][0])

    def test_momentum_with_insufficient_history_abstains(self):
        result = run_research_backtest([event()], [bar(i) for i in range(5)], FREE)
        self.assertEqual(result["benchmarks"]["price_only_momentum"]["summary"]["entries"], 0)

    def test_buy_and_hold_has_observed_start_fill_and_no_fake_end_sale(self):
        result = run_research_backtest([], [bar(0), bar(1, 110)], FREE)
        passive = result["benchmarks"]["buy_and_hold"]
        self.assertEqual(passive["open_position"]["entry_time"], stamps(0))
        self.assertAlmostEqual(passive["summary"]["return_pct"], 10)
        self.assertEqual(passive["trades"], [])
        self.assertEqual(result["summary"]["net_pnl"], 0)

    def test_metadata_is_retained_and_inputs_are_unchanged(self):
        item = event(evidence=[{"segment_id": "s1", "quote": "test quote"}])
        result = run_research_backtest([item], [bar(i) for i in range(5)], FREE)
        self.assertIsInstance(item["available_at"], datetime)
        self.assertEqual(result["per_video"][0]["metadata"]["evidence"], item["evidence"])
        json.dumps(result, allow_nan=False)

    def test_invalid_events_duplicate_sources_and_windows_fail_explicitly(self):
        prices = [bar(i) for i in range(5)]
        for inputs in ([event(), event()], [event(strength=float("nan"))], [event(strength=True)],
                       [event(strength=1.1)], [event(direction="buy")],
                       [event(), event("v2", variant="different")]):
            with self.subTest(inputs=inputs), self.assertRaises(ValueError):
                run_research_backtest(inputs, prices, FREE)
        with self.assertRaises(ValueError):
            ResearchConfig(sample_start=stamps(.5))
        with self.assertRaises(ValueError):
            run_research_backtest([], prices, replace(FREE, sample_end=stamps(6)))
        with self.assertRaises(ValueError):
            run_research_backtest([], [bar(0), bar(2), bar(3)], replace(FREE, sample_start=stamps(1)))


class MarketDownloadTests(unittest.TestCase):
    def test_rest_millisecond_close_is_normalized_to_exclusive_boundary(self):
        start = int(T0.timestamp() * 1000)
        raw = [start, "100", "102", "99", "101", "4", start + 3_600_000 - 1, "404", 2, "1", "101", "0"]
        normalized = normalize_row(raw, "BTCUSDT")
        self.assertEqual(normalized["open_time"], stamps(0))
        self.assertEqual(normalized["close_time"], stamps(1))
        self.assertEqual(normalized["volume"], 4)
        Bar.from_dict(normalized)
        raw[0] *= 1000
        raw[6] *= 1000
        with self.assertRaises(ValueError):
            normalize_row(raw, "BTCUSDT")

    def test_download_rejects_future_or_partial_candles_before_market_request(self):
        now = int((T0 + timedelta(minutes=30)).timestamp() * 1000)
        clock = ({"serverTime": now}, b'{"serverTime":0}', "https://example.invalid/time")
        with tempfile.TemporaryDirectory() as directory, patch(
                "scripts.fetch_market_bars.request_json", return_value=clock) as request:
            with self.assertRaises(ValueError):
                fetch(T0, T0 + timedelta(hours=1), Path(directory))
            self.assertEqual(request.call_count, 1)

    def test_download_records_a_gap_without_imputing_a_price(self):
        start = int(T0.timestamp() * 1000)
        rows = [[start + i * 3_600_000, "100", "102", "99", "101", "4",
                 start + (i + 1) * 3_600_000 - 1, "404", 2, "1", "101", "0"] for i in (0, 2)]
        payloads = [{"serverTime": start + 4 * 3_600_000},
                    {"symbols": [{"symbol": "BTCUSDT", "baseAsset": "BTC", "quoteAsset": "USDT",
                                  "isSpotTradingAllowed": True}]}, rows]
        responses = [(body, json.dumps(body).encode(), f"https://example.invalid/{i}")
                     for i, body in enumerate(payloads)]
        with tempfile.TemporaryDirectory() as directory, patch(
                "scripts.fetch_market_bars.request_json", side_effect=responses):
            manifest = fetch(T0, T0 + timedelta(hours=3), Path(directory))
            bars = json.loads((Path(directory) / "bars.json").read_text())
            self.assertEqual(len(bars), 2)
            self.assertEqual(manifest["bar_count"], 2)
            self.assertEqual(manifest["expected_bars"], 3)
            self.assertEqual(manifest["imputed_bars"], 0)
            self.assertEqual(manifest["gaps"], [{"start": stamps(1), "end": stamps(2), "missing_bars": 1}])


if __name__ == "__main__":
    unittest.main()
