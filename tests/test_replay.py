from dataclasses import FrozenInstanceError, replace
from datetime import datetime, timedelta, timezone
import json
import unittest

from signal_lab.engine import Policy
from signal_lab.models import Bar, Evidence, Signal
from signal_lab.replay import run_replay


T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def signal(**changes):
    item = Signal("s1", "video-1", "BTCUSDT", "long", "conditional", "close_above",
                  100, 90, 140, 60, 1440, T0, T0 + timedelta(days=1),
                  (Evidence("s1", "BTC closes above 100; stop 90; target 140."),), reviewed=True)
    return replace(item, **changes)


def bar(index=0, open=100, high=102, low=99, close=101):
    return Bar("BTCUSDT", T0 + timedelta(hours=index), T0 + timedelta(hours=index + 1),
               open, high, low, close)


def judgment(value="buy", **changes):
    probabilities = {"buy": 0.99, "sell": 0.005, "hold": 0.005}
    if value != "buy":
        probabilities[value], probabilities["buy"] = 0.99, 0.005
    return {"value": value, "confidence": 0.99, "abstained": False,
            "calibrated": True, "probabilities": probabilities, **changes}


def jev_judgment(**changes):
    return judgment(
        **{"confidence": .8, "probabilities": {"buy": .8, "sell": .1, "hold": .1},
           "calibrated": False, "provider": "typesafe", "model": "jev-1.14.0",
           "provider_confidence": .7, "probability_source": "jev_model",
           "calibration_source": "provider_claim_not_locally_validated", **changes}
    )


FREE = Policy(fee_bps=0, slippage_bps=0)


class PaperReplayTests(unittest.TestCase):
    def test_decide_at_close_fill_next_open_with_both_costs(self):
        result = run_replay([signal()], [bar(), bar(1, 102, 141, 101, 140)])
        trade = result["trades"][0]
        self.assertEqual(trade["entry_time"], "2026-01-01T01:00:00Z")
        self.assertAlmostEqual(trade["entry_price"], 102 * 1.0002)
        self.assertAlmostEqual(trade["exit_price"], 140 * .9998)
        self.assertGreater(trade["entry_fee"], 0)
        self.assertGreater(trade["exit_fee"], 0)
        self.assertAlmostEqual(trade["net_pnl"], trade["gross_pnl"] - trade["fees"])
        self.assertAlmostEqual(result["summary"]["final_equity"], 10_000 + trade["net_pnl"])

    def test_last_close_cannot_create_same_bar_fill(self):
        result = run_replay([signal()], [bar()])
        self.assertEqual(result["summary"]["entries"], 0)
        self.assertEqual(result["events"][-1]["reasons"], ["end_of_data"])

    def test_model_receives_only_completed_immutable_current_bar(self):
        seen = []

        def judge(s, b):
            seen.append((s.available_at, b.close_time, b.close))
            with self.assertRaises(FrozenInstanceError):
                b.close = 999
            return judgment()

        result = run_replay([signal()], [bar(), bar(1, 102, 141, 101, 140)], judge=judge)
        self.assertEqual(seen, [(T0, T0 + timedelta(hours=1), 101)])
        self.assertEqual(result["summary"]["model_calls"], 1)

    def test_different_future_prices_cannot_change_initial_decision(self):
        a = run_replay([signal()], [bar(), bar(1, 102, 103, 91, 95)], FREE)
        b = run_replay([signal()], [bar(), bar(1, 102, 145, 101, 144)], FREE)
        self.assertEqual(a["events"][0], b["events"][0])
        self.assertEqual(a["events"][1], b["events"][1])

    def test_future_signal_is_never_shown_to_judge_or_events(self):
        future = signal(available_at=T0 + timedelta(hours=4))
        result = run_replay([future], [bar(), bar(1)], judge=lambda *_: self.fail("Future leaked"))
        self.assertEqual(result["events"], [])
        self.assertEqual(result["summary"]["entries"], 0)

    def test_missing_required_levels_never_calls_model(self):
        result = run_replay([signal(stop=None)], [bar(), bar(1)], judge=lambda *_: self.fail("No stop"))
        self.assertIn("stop_missing", result["events"][0]["reasons"])

    def test_intrabar_stop_target_collision_uses_stop_first(self):
        result = run_replay([signal()], [bar(), bar(1, 101, 150, 80, 120)], FREE)
        self.assertEqual(result["trades"][0]["exit_reason"], "stop_before_target")
        self.assertEqual(result["trades"][0]["exit_price"], 90)
        self.assertLess(result["trades"][0]["net_pnl"], 0)
        self.assertEqual(result["trades"][0]["exit_time_basis"], "bar_close_bound")

    def test_stop_gap_exposes_loss_beyond_planned_risk(self):
        result = run_replay([signal()], [bar(), bar(1, 101, 102, 99, 100),
                                        bar(2, 75, 80, 70, 78)], FREE)
        trade = result["trades"][0]
        self.assertEqual((trade["exit_reason"], trade["exit_price"]), ("stop_gap", 75))
        self.assertLess(trade["net_pnl"], -25)

    def test_known_target_at_open_precedes_later_intrabar_stop(self):
        result = run_replay([signal()], [bar(), bar(1),
                                        bar(2, 145, 150, 80, 85)], FREE)
        trade = result["trades"][0]
        self.assertEqual((trade["exit_reason"], trade["exit_price"]), ("target_gap", 140))
        self.assertEqual(trade["exit_time_basis"], "bar_open")

    def test_normal_stop_loss_size_includes_fees_and_slippage(self):
        result = run_replay([signal()], [bar(), bar(1, 101, 102, 89, 92)])
        self.assertAlmostEqual(result["trades"][0]["net_pnl"], -25, places=9)

    def test_exposure_cap_prevents_oversized_tight_stop(self):
        policy = replace(FREE, risk_fraction=.5, max_exposure_fraction=.2)
        result = run_replay([signal(stop=99, target=200)], [bar(), bar(1, 101, 102, 100, 101)], policy)
        entry = next(e for e in result["events"] if e["type"] == "entry")
        self.assertLessEqual(entry["notional"], 2_000)

    def test_entry_gap_past_target_is_cancelled(self):
        result = run_replay([signal()], [bar(), bar(1, 150, 155, 145, 151)], FREE)
        self.assertEqual(result["summary"]["entries"], 0)
        self.assertIn("entry_gap_outside_bracket", result["events"][-1]["reasons"])

    def test_fill_reward_risk_is_rechecked_after_gap(self):
        result = run_replay([signal()], [bar(), bar(1, 125, 130, 120, 126)], FREE)
        self.assertEqual(result["summary"]["entries"], 0)
        self.assertIn("fill_reward_risk_too_low", result["events"][-1]["reasons"])

    def test_missing_next_bar_cancels_order_instead_of_delayed_chasing(self):
        result = run_replay([signal()], [bar(), bar(3)], FREE)
        self.assertEqual(result["summary"]["entries"], 0)
        self.assertIn("noncontiguous_next_bar", result["events"][-1]["reasons"])

    def test_expiry_exits_on_first_bar_open_at_or_after_deadline(self):
        s = signal(expires_at=T0 + timedelta(minutes=150), horizon_minutes=150)
        result = run_replay([s], [bar(), bar(1), bar(2), bar(3)], FREE)
        self.assertEqual(result["trades"][0]["exit_time"], "2026-01-01T03:00:00Z")
        self.assertEqual(result["trades"][0]["exit_reason"], "expired")

    def test_open_losses_are_marked_without_fictitious_end_liquidation(self):
        result = run_replay([signal()], [bar(), bar(1, 101, 102, 92, 94)], FREE)
        self.assertEqual(result["summary"]["completed_trades"], 0)
        self.assertLess(result["summary"]["final_equity"], 10_000)
        self.assertLess(result["open_position"]["unrealized_pnl"], 0)
        self.assertGreater(result["summary"]["max_drawdown_pct"], 0)

    def test_drawdown_halt_flattens_and_blocks_all_later_entries(self):
        s = signal(level=99, stop=50, target=220)
        second = replace(s, id="s2", available_at=T0 + timedelta(hours=2))
        policy = replace(FREE, risk_fraction=.5, max_drawdown_fraction=.05)
        result = run_replay([s, second], [bar(close=100), bar(1, 100, 101, 89, 90),
                                         bar(2, 100, 101, 99, 100)], policy)
        self.assertTrue(result["summary"]["halted"])
        self.assertEqual(result["summary"]["entries"], 1)
        self.assertEqual(result["trades"][0]["exit_reason"], "max_drawdown")
        self.assertIsNone(result["open_position"])

    def test_short_profit_and_fees_use_correct_sign(self):
        s = signal(side="short", trigger="close_below", level=102, stop=112, target=70)
        result = run_replay([s], [bar(), bar(1, 100, 101, 69, 72)], Policy(allow_short=True))
        trade = result["trades"][0]
        self.assertLess(trade["entry_price"], 100)
        self.assertGreater(trade["exit_price"], 70)
        self.assertGreater(trade["net_pnl"], 0)
        self.assertAlmostEqual(result["summary"]["net_pnl"], trade["net_pnl"])

    def test_drawdown_observed_at_close_fills_risk_exit_at_next_open_including_gap(self):
        s = signal(level=99, stop=50, target=220)
        policy = replace(FREE, risk_fraction=.5, max_drawdown_fraction=.05)
        result = run_replay([s], [bar(close=100), bar(1, 100, 101, 89, 90),
                                 bar(2, 70, 75, 60, 65)], policy)
        trade = result["trades"][0]
        self.assertEqual(trade["exit_price"], 70)
        self.assertEqual(trade["exit_time"], (T0 + timedelta(hours=2)).isoformat().replace("+00:00", "Z"))
        self.assertEqual(trade["exit_time_basis"], "bar_open")
        self.assertEqual(trade["net_pnl"], -3000)

    def test_last_bar_drawdown_does_not_invent_a_liquidation(self):
        s = signal(level=99, stop=50, target=220)
        policy = replace(FREE, risk_fraction=.5, max_drawdown_fraction=.05)
        result = run_replay([s], [bar(close=100), bar(1, 100, 101, 89, 90)], policy)
        self.assertTrue(result["summary"]["halted"])
        self.assertIsNotNone(result["open_position"])
        self.assertEqual(result["trades"], [])
        self.assertTrue(any(e["type"] == "risk_exit_unfilled" for e in result["events"]))

    def test_policy_abstention_keeps_sanitized_cause_and_provenance(self):
        answer = judgment("hold", confidence=0.0, calibrated=False, abstained=True,
                          probabilities={"buy": 0.0, "sell": 0.0, "hold": 1.0},
                          probability_source="fail_closed_policy", error_code="model_abstained")
        result = run_replay([signal()], [bar(), bar(1)], FREE,
                            judge=lambda *_: answer)
        event = next(e for e in result["events"] if e["type"] == "model_judgment")
        self.assertEqual(event["reasons"], ["model_policy_abstention"])
        self.assertEqual(event["error_code"], "model_abstained")
        self.assertEqual(event["probability_source"], "fail_closed_policy")
        self.assertEqual(result["summary"]["entries"], 0)

    def test_signal_is_never_reentered_after_stop(self):
        result = run_replay([signal()], [bar(), bar(1, 101, 103, 89, 92), bar(2), bar(3)], FREE)
        self.assertEqual(result["summary"]["entries"], 1)

    def test_one_position_even_if_multiple_same_side_signals_are_eligible(self):
        result = run_replay([signal(), signal(id="s2")], [bar(), bar(1), bar(2)], FREE)
        self.assertEqual(result["summary"]["entries"], 1)

    def test_opposing_simultaneously_eligible_signals_abstain(self):
        short = signal(id="s2", side="short", trigger="close_below", level=110, stop=150, target=20)
        result = run_replay([signal(), short], [bar(), bar(1)], replace(FREE, allow_short=True))
        self.assertEqual(result["summary"]["entries"], 0)
        self.assertEqual(result["summary"]["rejected_signals"], 2)
        self.assertTrue(all(e["reasons"] == ["conflicting_directions"] for e in result["events"]))

    def test_outage_is_a_veto_and_error_text_does_not_leak(self):
        def broken(*_):
            raise RuntimeError("secret=do-not-copy")
        result = run_replay([signal()], [bar(), bar(1)], judge=broken)
        self.assertEqual(result["summary"]["entries"], 0)
        self.assertIn("model_error", result["events"][0]["reasons"])
        self.assertNotIn("do-not-copy", json.dumps(result))

    def test_model_abstention_uncalibrated_hold_and_low_confidence_veto(self):
        answers = [judgment(abstained=True), judgment(calibrated=False), judgment("hold"),
                   judgment(confidence=.5, probabilities={"buy": .5, "sell": .3, "hold": .2})]
        for answer in answers:
            with self.subTest(answer=answer):
                result = run_replay([signal()], [bar(), bar(1)], judge=lambda *_: answer)
                self.assertEqual(result["summary"]["entries"], 0)

    def test_jev_paper_experiment_preserves_both_scores_and_calibration_limit(self):
        result = run_replay([signal()], [bar(), bar(1)], judge=lambda *_: jev_judgment())
        self.assertEqual(result["summary"]["entries"], 1)
        event = next(e for e in result["events"] if e["type"] == "model_judgment")
        self.assertEqual(event["reasons"], ["model_agreed"])
        self.assertEqual(event["confidence"], .8)
        self.assertEqual(event["provider_confidence"], .7)
        self.assertEqual(event["model"], "jev-1.14.0")
        self.assertEqual(event["provider"], "typesafe")
        self.assertEqual(event["probability_source"], "jev_model")
        self.assertEqual(event["calibration_source"], "provider_claim_not_locally_validated")
        self.assertFalse(event["calibrated"])

    def test_jev_gate_uses_selected_probability_not_provider_confidence(self):
        answer = jev_judgment(confidence=.75, provider_confidence=.99,
                              probabilities={"buy": .75, "sell": .125, "hold": .125})
        result = run_replay([signal()], [bar(), bar(1)], judge=lambda *_: answer)
        self.assertEqual(result["summary"]["entries"], 0)
        self.assertEqual(result["events"][0]["reasons"], ["model_low_confidence"])

    def test_unknown_or_malformed_jev_provenance_does_not_relax_calibration_gate(self):
        for change in ({"provider": "unknown"}, {"model": "jev-latest"},
                       {"calibration_source": "assumed"}, {"probability_source": "heuristic"},
                       {"provider_confidence": float("nan")}, {"provider_confidence": True},
                       {"provider_confidence": 2}, {"provider_confidence": None}):
            with self.subTest(change=change):
                result = run_replay([signal()], [bar(), bar(1)], judge=lambda *_: jev_judgment(**change))
                self.assertEqual(result["summary"]["entries"], 0)
                self.assertEqual(result["events"][0]["reasons"], ["model_uncalibrated"])
                json.dumps(result, allow_nan=False)

    def test_jev_agreement_cannot_override_risk_check_at_fill(self):
        result = run_replay([signal()], [bar(), bar(1, 150, 155, 145, 151)], FREE,
                            judge=lambda *_: jev_judgment())
        self.assertEqual(result["summary"]["entries"], 0)
        self.assertIn("entry_gap_outside_bracket", result["events"][-1]["reasons"])

    def test_abstaining_callback_with_oversized_provider_score_does_not_break_audit(self):
        result = run_replay([signal()], [bar(), bar(1)],
                            judge=lambda *_: jev_judgment(abstained=True, provider_confidence=10**400))
        self.assertEqual(result["summary"]["entries"], 0)
        event = next(e for e in result["events"] if e["type"] == "model_judgment")
        self.assertEqual(event["reasons"], ["model_abstained"])
        self.assertNotIn("provider_confidence", event)
        json.dumps(result, allow_nan=False)

    def test_policy_hold_retains_valid_rejected_model_evidence_without_raw_diagnostics(self):
        original = jev_judgment(value="sell", confidence=.9, provider_confidence=.85,
                                 probabilities={"buy": .05, "sell": .9, "hold": .05},
                                 debug="secret-provider-diagnostics")
        answer = judgment("hold", confidence=0.0, calibrated=False, abstained=True,
                          probabilities={"buy": 0.0, "sell": 0.0, "hold": 1.0},
                          probability_source="fail_closed_policy", error_code="opposite_direction",
                          model_decision=original)
        result = run_replay([signal()], [bar(), bar(1)], judge=lambda *_: answer)
        event = next(e for e in result["events"] if e["type"] == "model_judgment")
        self.assertEqual(result["summary"]["entries"], 0)
        self.assertEqual(event["value"], "hold")
        self.assertEqual(event["probability_source"], "fail_closed_policy")
        self.assertEqual(event["model_decision"]["value"], "sell")
        self.assertEqual(event["model_decision"]["probabilities"], original["probabilities"])
        self.assertEqual(event["model_decision"]["provider_confidence"], .85)
        self.assertFalse(event["model_decision"]["calibrated"])
        self.assertNotIn("secret-provider-diagnostics", json.dumps(result))

    def test_policy_hold_drops_invalid_nested_model_evidence(self):
        for original in (None, {"error": "secret-provider-diagnostics"},
                         jev_judgment(probabilities={"buy": 10**400, "sell": 0, "hold": 0}),
                         jev_judgment(probability_source="invented"),
                         jev_judgment(provider_confidence=float("nan"))):
            with self.subTest(original=original):
                answer = judgment("hold", confidence=0.0, calibrated=False, abstained=True,
                                  probabilities={"buy": 0.0, "sell": 0.0, "hold": 1.0},
                                  probability_source="fail_closed_policy", error_code="opposite_direction",
                                  model_decision=original)
                result = run_replay([signal()], [bar(), bar(1)], judge=lambda *_: answer)
                self.assertEqual(result["summary"]["entries"], 0)
                self.assertNotIn("model_decision", result["events"][0])
                self.assertNotIn("secret-provider-diagnostics", json.dumps(result, allow_nan=False))

    def test_malformed_model_probabilities_fail_closed(self):
        answers = [None, {}, judgment(probabilities={"buy": 1}),
                   judgment(probabilities={"buy": float("nan"), "sell": 0, "hold": 0}),
                   judgment(probabilities={"buy": .99, "sell": .5, "hold": .5}),
                   judgment(confidence=.8), judgment(calibrated="true"),
                   judgment(probabilities={"buy": True, "sell": 0, "hold": 0})]
        for answer in answers:
            with self.subTest(answer=answer):
                result = run_replay([signal()], [bar(), bar(1)], judge=lambda *_: answer)
                self.assertEqual(result["summary"]["entries"], 0)
                json.dumps(result, allow_nan=False)

    def test_model_cannot_override_deterministic_review_gate(self):
        result = run_replay([signal(reviewed=False)], [bar(), bar(1)], judge=lambda *_: self.fail("Unreviewed"))
        self.assertEqual(result["summary"]["entries"], 0)

    def test_untriggered_signal_has_inspectable_wait_reason(self):
        result = run_replay([signal(level=110)], [bar(), bar(1)], FREE)
        self.assertEqual(result["events"][0]["reasons"], ["trigger_not_met"])
        self.assertEqual(len(result["events"]), 1)

    def test_bad_series_and_duplicate_ids_fail_loud(self):
        for signals, bars in [([signal(), signal()], [bar()]), ([signal()], []),
                              ([signal()], [bar(1), bar(0)]),
                              ([signal()], [bar(), replace(bar(1), asset="ETHUSDT")])]:
            with self.subTest(signals=signals, bars=bars), self.assertRaises(ValueError):
                run_replay(signals, bars)

    def test_output_is_finite_json_and_reproducible(self):
        a = run_replay([signal()], [bar(), bar(1)])
        b = run_replay([signal()], [bar(), bar(1)])
        self.assertEqual(json.dumps(a, allow_nan=False), json.dumps(b, allow_nan=False))


if __name__ == "__main__":
    unittest.main()
