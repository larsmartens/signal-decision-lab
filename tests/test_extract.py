"""Adversarial extraction and provenance checks against docs/SPEC.md.

All operational timestamps and prices are synthetic. One short, attributed
Krown quotation checks genuine source wording; it is not a validated trade.
"""
from dataclasses import replace
from datetime import timedelta
import unittest

from signal_lab.extract import extract_rules, review_signal, validate_grounding
from signal_lab.models import Evidence, Segment, Transcript, utc


PUBLISHED = utc("2026-11-13T10:00:00Z")
AVAILABLE = utc("2026-11-13T10:02:00Z")
REVIEWED = utc("2026-11-13T10:05:00Z")
COMPLETE = (
    "Buy BTC if the 1h candle closes above 100; "
    "stop at 95; target 120; valid for 4 hours."
)


def transcript(text, *, available=AVAILABLE):
    return Transcript(
        "synthetic-extraction-test", "Synthetic test", "https://example.invalid/test",
        PUBLISHED, available, (Segment("s1", 0, 12, text),), "synthetic",
    )


class ExtractionBehaviorTests(unittest.TestCase):
    def assert_not_reviewable(self, text):
        source = transcript(text)
        for signal in extract_rules(source):
            with self.assertRaises(ValueError, msg=text):
                review_signal(signal, source, reviewed_at=REVIEWED)

    def test_explicit_supported_setup_preserves_fields_and_requires_review(self):
        source = transcript(COMPLETE)
        [signal] = extract_rules(source)
        self.assertEqual(signal.asset, "BTCUSDT")
        self.assertEqual(signal.statement_type, "conditional")
        self.assertEqual(signal.side, "long")
        self.assertEqual(signal.trigger, "close_above")
        self.assertEqual((signal.level, signal.stop, signal.target), (100, 95, 120))
        self.assertEqual((signal.timeframe_minutes, signal.horizon_minutes), (60, 240))
        self.assertFalse(signal.reviewed)
        self.assertEqual(signal.issues, ())
        self.assertEqual(signal.evidence, (Evidence("s1", COMPLETE),))
        self.assertTrue(review_signal(signal, source, reviewed_at=REVIEWED).reviewed)

    def test_unknown_fields_are_not_filled_by_defaults(self):
        source = transcript("I think Bitcoin has good long-term value.")
        [signal] = extract_rules(source)
        for name in ("level", "stop", "target", "timeframe_minutes", "horizon_minutes", "expires_at"):
            with self.subTest(field=name):
                self.assertIsNone(getattr(signal, name))
        with self.assertRaises(ValueError):
            review_signal(signal, source, reviewed_at=REVIEWED)

    def test_negated_entry_variants_cannot_be_reviewed(self):
        prefixes = (
            "Do not buy BTC", "I would not buy BTC", "Do not go long BTC",
            "I can no longer buy BTC", "I cannot buy BTC", "Don't take a long BTC",
        )
        suffix = " if the 1h candle closes above 100; stop at 95; target 120; valid for 4 hours."
        for prefix in prefixes:
            with self.subTest(prefix=prefix):
                self.assert_not_reviewable(prefix + suffix)

    def test_retrospective_trade_variants_cannot_be_reviewed(self):
        texts = (
            "Yesterday I went long BTC when the 1h candle closes above 100; stop at 95; target 120; valid for 4 hours.",
            "Earlier today I went long BTC when the 1h candle closes above 100; stop at 95; target 120; valid for 4 hours.",
            "Last month I used this rule: " + COMPLETE,
        )
        for text in texts:
            with self.subTest(text=text):
                self.assert_not_reviewable(text)

    def test_hypothetical_educational_and_reported_speech_are_not_entries(self):
        for prefix in ("For example, ", "Hypothetically, ", "In this educational example, ", "Another trader said: "):
            with self.subTest(prefix=prefix):
                self.assert_not_reviewable(prefix + COMPLETE)

    def test_additional_unrepresented_conditions_block_review(self):
        for condition in (
            " and the weekly trend is bullish",
            " and volatility is low",
            " and the Fed cuts interest rates",
            " and RSI is above 50",
            " unless momentum is bearish",
        ):
            text = COMPLETE.replace("above 100;", "above 100" + condition + ";")
            with self.subTest(condition=condition):
                self.assert_not_reviewable(text)

    def test_percentages_and_ranges_do_not_become_exact_absolute_prices(self):
        for expression in ("95%", "95 percent", "95 bps", "95 basis points", "95 to 96", "95-96", "95–96"):
            text = COMPLETE.replace("stop at 95", "stop at " + expression)
            source = transcript(text)
            with self.subTest(expression=expression):
                [signal] = extract_rules(source)
                self.assertTrue(signal.stop is None or signal.issues,
                                "An ambiguous/relative stop became an exact absolute price")
                with self.assertRaises(ValueError):
                    review_signal(signal, source, reviewed_at=REVIEWED)

    def test_trigger_range_cannot_silently_become_its_first_boundary(self):
        self.assert_not_reviewable(COMPLETE.replace("above 100;", "above 100 to 105;"))

    def test_spoken_price_correction_cannot_be_ignored(self):
        self.assert_not_reviewable(COMPLETE.replace("stop at 95;", "stop at 95, sorry, 90;"))

    def test_conflicting_validity_windows_cannot_silently_choose_the_first(self):
        self.assert_not_reviewable(COMPLETE + " This setup is valid for 24 hours.")

    def test_decimal_timeframe_is_not_misread_as_its_fractional_digit(self):
        source = transcript(COMPLETE.replace("1h", "0.5h"))
        [signal] = extract_rules(source)
        self.assertTrue(signal.timeframe_minutes in (None, 30) or signal.issues,
                        "0.5h was misread as 5h")

    def test_real_krown_uncertainty_quote_is_not_an_actionable_trade(self):
        # Genuine source wording, 10 words; all harness metadata is synthetic.
        # https://www.buzzsprout.com/2646521/episodes/19753958-bitcoin-likely-to-4x-in-the-next-2-years-erik-crown-breaks-down-the-data-proof-of-thesis?t=0
        # Publisher speaker block 04:38–08:43; syndicated VTT ~08:18.480–08:20.560.
        # Cointelegraph dates the episode 2026-09-02; Buzzsprout 2026-09-04.
        quote = "Now, does Bitcoin finish above six digits? I don't know."
        source = transcript(quote)
        [signal] = extract_rules(source)
        self.assertEqual(signal.statement_type, "commentary")
        self.assertEqual(signal.side, "none")
        self.assertIsNone(signal.level)
        self.assertIsNone(signal.stop)
        self.assertIsNone(signal.target)
        self.assertFalse(signal.reviewed)
        with self.assertRaises(ValueError):
            review_signal(signal, source, reviewed_at=REVIEWED)


class GroundingAndTimeTests(unittest.TestCase):
    def test_number_must_match_its_role_not_just_appear_in_evidence(self):
        source = transcript(COMPLETE)
        [signal] = extract_rules(source)
        for mutation in ({"stop": 120}, {"target": 95}, {"level": 95}, {"trigger": "close_below"}):
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):
                    validate_grounding(replace(signal, **mutation), source)

    def test_fake_quote_wrong_segment_and_wrong_source_are_rejected(self):
        source = transcript(COMPLETE)
        [signal] = extract_rules(source)
        for mutation in (
            {"evidence": (Evidence("s1", "Buy BTC at 99"),)},
            {"evidence": (Evidence("missing", COMPLETE),)},
            {"source_id": "different-video"},
        ):
            with self.subTest(mutation=mutation):
                with self.assertRaises(ValueError):
                    validate_grounding(replace(signal, **mutation), source)

    def test_cropping_evidence_cannot_remove_negation_or_history(self):
        for prefix in ("Do not ", "Yesterday I said: "):
            quoted = COMPLETE[0].lower() + COMPLETE[1:]
            source = transcript(prefix + quoted)
            [signal] = extract_rules(source)
            forged = replace(signal, statement_type="conditional", side="long", issues=(),
                             evidence=(Evidence("s1", quoted),))
            with self.subTest(prefix=prefix):
                with self.assertRaises(ValueError):
                    review_signal(forged, source, reviewed_at=REVIEWED)

    def test_cropping_evidence_cannot_remove_an_unsupported_condition(self):
        source = transcript(COMPLETE + " Only enter if RSI is above 50.")
        [signal] = extract_rules(source)
        forged = replace(signal, issues=(), evidence=(Evidence("s1", COMPLETE),))
        with self.assertRaises(ValueError):
            review_signal(forged, source, reviewed_at=REVIEWED)

    def test_clearing_ambiguity_flag_cannot_select_an_unresolved_setup(self):
        source = transcript(COMPLETE + " Or buy BTC if the 1h candle closes above 105.")
        [signal] = extract_rules(source)
        forged = replace(signal, trigger="close_above", level=100, issues=())
        with self.assertRaises(ValueError):
            review_signal(forged, source, reviewed_at=REVIEWED)

    def test_extraction_availability_is_not_backdated(self):
        source = transcript(COMPLETE)
        [signal] = extract_rules(source, extracted_at=PUBLISHED)
        self.assertEqual(signal.available_at, AVAILABLE)
        with self.assertRaises(ValueError):
            validate_grounding(replace(signal, available_at=PUBLISHED), source)

    def test_delayed_extraction_does_not_restart_the_source_horizon(self):
        source = transcript(COMPLETE)
        [early] = extract_rules(source, extracted_at=AVAILABLE)
        [late] = extract_rules(source, extracted_at=AVAILABLE + timedelta(hours=1))
        expected = PUBLISHED + timedelta(hours=4)
        self.assertEqual(early.expires_at, expected)
        self.assertEqual(late.expires_at, expected)
        self.assertEqual(late.available_at, AVAILABLE + timedelta(hours=1))

    def test_delayed_review_does_not_restart_the_source_horizon(self):
        source = transcript(COMPLETE)
        [signal] = extract_rules(source)
        reviewed = review_signal(signal, source, reviewed_at=AVAILABLE + timedelta(hours=1))
        self.assertEqual(reviewed.expires_at, PUBLISHED + timedelta(hours=4))
        self.assertEqual(reviewed.available_at, AVAILABLE + timedelta(hours=1))
        self.assertEqual(reviewed.extracted_at, AVAILABLE)
        self.assertEqual(reviewed.reviewed_at, AVAILABLE + timedelta(hours=1))

    def test_already_expired_capture_is_auditable_but_not_reviewable(self):
        source = transcript(COMPLETE, available=PUBLISHED + timedelta(hours=5))
        [signal] = extract_rules(source)
        self.assertEqual(signal.expires_at, PUBLISHED + timedelta(hours=4))
        with self.assertRaises(ValueError):
            review_signal(signal, source, reviewed_at=source.available_at)

    def test_review_before_availability_and_expiry_drift_are_rejected(self):
        source = transcript(COMPLETE)
        [signal] = extract_rules(source)
        with self.assertRaises(ValueError):
            review_signal(signal, source, reviewed_at=PUBLISHED)
        with self.assertRaises(ValueError):
            validate_grounding(replace(signal, expires_at=signal.expires_at + timedelta(hours=1)), source)


if __name__ == "__main__":
    unittest.main()
