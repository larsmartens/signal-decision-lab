from dataclasses import replace
from datetime import datetime, timedelta, timezone
import unittest

from signal_lab.engine import Policy, decide
from signal_lab.models import Bar, Evidence, Signal


T0 = datetime(2026, 1, 1, tzinfo=timezone.utc)


def signal(**changes):
    item = Signal("s1", "video-1", "BTCUSDT", "long", "conditional", "close_above",
                  100, 90, 130, 60, 1440, T0, T0 + timedelta(days=1),
                  (Evidence("s1", "BTC closes above 100; stop 90; target 130."),), reviewed=True)
    return replace(item, **changes)


def bar(index=0, open=100, high=102, low=99, close=101):
    return Bar("BTCUSDT", T0 + timedelta(hours=index), T0 + timedelta(hours=index + 1),
               open, high, low, close)


class EligibilityTests(unittest.TestCase):
    def test_complete_reviewed_conditional_signal_enters(self):
        self.assertEqual(decide(signal(), bar()).action, "enter_long")

    def test_exact_level_is_not_a_close_above(self):
        self.assertEqual(decide(signal(), bar(close=100)).reasons, ("trigger_not_met",))

    def test_future_statement_is_not_visible(self):
        result = decide(signal(available_at=T0 + timedelta(hours=2)), bar())
        self.assertEqual((result.action, result.reasons), ("wait", ("not_available",)))

    def test_availability_exactly_at_close_is_permitted(self):
        result = decide(signal(available_at=bar().close_time), bar())
        self.assertEqual(result.action, "enter_long")

    def test_expiry_at_close_blocks_entry(self):
        self.assertIn("expired", decide(signal(expires_at=bar().close_time), bar()).reasons)

    def test_stated_horizon_also_bounds_later_expiry(self):
        self.assertIn("expired", decide(signal(horizon_minutes=60), bar()).reasons)

    def test_late_capture_does_not_renew_expired_source_window(self):
        late = signal(available_at=T0 + timedelta(hours=3),
                      expires_at=T0 + timedelta(hours=2))
        self.assertIn("expired", decide(late, bar(3)).reasons)

    def test_extraction_cannot_approve_itself(self):
        self.assertIn("review_required", decide(signal(reviewed=False), bar()).reasons)

    def test_issues_cannot_be_overridden_by_review(self):
        self.assertIn("extraction_issues", decide(signal(issues=("ambiguous_stop",)), bar()).reasons)

    def test_commentary_negation_and_retrospective_are_not_orders(self):
        for kind in ("commentary", "negated", "retrospective"):
            with self.subTest(kind=kind):
                self.assertIn("not_actionable", decide(signal(statement_type=kind), bar()).reasons)

    def test_missing_fields_are_not_given_defaults(self):
        for field in ("level", "stop", "target", "timeframe_minutes", "horizon_minutes", "expires_at"):
            with self.subTest(field=field):
                self.assertIn(field + "_missing", decide(signal(**{field: None}), bar()).reasons)

    def test_wrong_asset_and_timeframe_are_blocked(self):
        self.assertIn("asset_mismatch", decide(signal(asset="ETHUSDT"), bar()).reasons)
        self.assertIn("timeframe_mismatch", decide(signal(timeframe_minutes=240), bar()).reasons)

    def test_unsupported_trigger_and_direction_are_blocked(self):
        result = decide(signal(trigger="none", side="none"), bar())
        self.assertIn("trigger_missing", result.reasons)
        self.assertIn("direction_missing", result.reasons)

    def test_inverted_bracket_is_blocked(self):
        self.assertIn("invalid_bracket", decide(signal(stop=105), bar()).reasons)

    def test_price_already_beyond_target_is_blocked(self):
        result = decide(signal(), bar(open=130, high=132, low=129, close=131))
        self.assertIn("price_outside_bracket", result.reasons)

    def test_reward_risk_is_checked_at_decision_price(self):
        result = decide(signal(), bar(open=119, high=121, low=118, close=120))
        self.assertIn("reward_risk_too_low", result.reasons)

    def test_short_requires_explicit_simulation_opt_in(self):
        short = signal(side="short", trigger="close_below", level=102, stop=112, target=70)
        self.assertIn("short_disabled", decide(short, bar()).reasons)
        self.assertEqual(decide(short, bar(), policy=Policy(allow_short=True)).action, "enter_short")

    def test_policy_rejects_invalid_numbers_and_truthy_strings(self):
        for kwargs in ({"risk_fraction": 0}, {"risk_fraction": 2}, {"fee_bps": -1},
                       {"slippage_bps": 10_000}, {"initial_equity": float("nan")},
                       {"min_model_confidence": True}, {"allow_short": "yes"}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                Policy(**kwargs)


if __name__ == "__main__":
    unittest.main()
