"""Behavioral checks for research bias extraction; all wording is synthetic."""
from dataclasses import replace
from datetime import datetime, timezone
import unittest

from signal_lab.krown_extract import (
    BIAS_CONFIGS,
    aggregate_bias,
    extract_bias,
    extract_bias_events,
    validate_bias_grounding,
)
from signal_lab.models import Segment, Transcript


def transcript(*texts: str) -> Transcript:
    at = datetime(2025, 1, 1, tzinfo=timezone.utc)
    return Transcript(
        source_id="synthetic-video", channel="Synthetic analyst", url="https://example.invalid/video",
        published_at=at, available_at=at, kind="synthetic",
        segments=tuple(Segment(f"s{i}", i * 30, i * 30 + 20, text) for i, text in enumerate(texts)),
    )


class CurrentBiasTests(unittest.TestCase):
    def test_current_direction_is_a_research_view_without_trade_fields(self):
        source = transcript("I am bullish on Bitcoin right now.")
        summary = extract_bias(source)
        self.assertEqual(summary.direction, "long")
        self.assertEqual(summary.supporting_count, 1)
        [event] = extract_bias_events(source)
        self.assertTrue(event.accepted)
        self.assertEqual(event.asset, "BTCUSDT")
        self.assertEqual(event.direction, "long")
        self.assertFalse(hasattr(event, "stop"))
        self.assertFalse(hasattr(event, "reviewed"))
        self.assertIn("heuristic_score_not_probability", summary.issues)
        validate_bias_grounding(event, source)

    def test_negation_split_across_caption_segments_does_not_reverse_polarity(self):
        source = transcript("For Bitcoin, I am not", "bullish right now.")
        summary = extract_bias(source)
        self.assertEqual(summary.direction, "flat")
        self.assertEqual(summary.excluded_count, 1)
        [event] = extract_bias_events(source)
        self.assertEqual(event.candidate_direction, "long")
        self.assertIn("negated_context", event.issues)
        self.assertTrue(any("not" in span.quote for span in event.evidence))

    def test_history_conditional_examples_and_reported_speech_abstain(self):
        cases = {
            "Yesterday I was bullish on Bitcoin.": "historical_context",
            "If Bitcoin closes above 100, I am bullish.": "conditional_context",
            "Bitcoin looks bullish unless support breaks.": "conditional_context",
            "For example, I am bullish on Bitcoin.": "hypothetical_or_educational_context",
            "Another trader says Bitcoin is bullish.": "reported_speech",
            "I would be bullish on Bitcoin.": "hypothetical_or_educational_context",
            "Is Bitcoin bullish today?": "question_or_uncertainty",
        }
        for text, reason in cases.items():
            with self.subTest(text=text):
                source = transcript(text)
                self.assertEqual(extract_bias(source).direction, "flat")
                self.assertTrue(any(reason in e.issues for e in extract_bias_events(source)))

    def test_but_does_not_erase_a_conditional_branch(self):
        source = transcript("If Bitcoin closes above 100 I am bullish, but below 90 I am bearish.")
        self.assertEqual(extract_bias(source).direction, "flat")
        self.assertEqual(extract_bias(source).excluded_count, 2)

    def test_explicit_current_contrast_can_follow_a_historical_view(self):
        source = transcript("Yesterday I was bullish on Bitcoin, but now I expect Bitcoin to move lower.")
        summary = extract_bias(source)
        self.assertEqual(summary.direction, "short")
        self.assertEqual(summary.supporting_count, 1)
        self.assertEqual(summary.excluded_count, 1)

    def test_opposite_words_are_not_flipped_into_an_unstated_view(self):
        for text in ("I am not bearish on Bitcoin.", "Bitcoin is neither bullish nor bearish."):
            with self.subTest(text=text):
                self.assertEqual(extract_bias(transcript(text)).direction, "flat")

    def test_uncertain_or_merely_possible_direction_does_not_create_a_view(self):
        for text in ("I don't know if Bitcoin is bullish or bearish.", "Bitcoin could go higher."):
            for config in ("context_strict", "context_standard", "context_broad"):
                with self.subTest(text=text, config=config):
                    self.assertEqual(extract_bias(transcript(text), config).direction, "flat")

    def test_technical_descriptions_do_not_imply_a_price_forecast(self):
        for text in (
            "Bitcoin has a bullish divergence on the RSI.",
            "For Bitcoin I am looking at the higher timeframes.",
            "Bitcoin is forming a lower high.",
            "Bitcoin has higher volatility today.",
            "For Bitcoin, I think the stochastic has a bullish reset.",
        ):
            with self.subTest(text=text):
                self.assertEqual(extract_bias(transcript(text), "context_broad").direction, "flat")

    def test_caption_line_breaks_do_not_remove_trailing_conditions(self):
        source = transcript("I am bullish on Bitcoin\nas long as support holds.")
        self.assertEqual(extract_bias(source).direction, "flat")

    def test_a_follow_on_claim_keeps_the_condition_on_its_asset_reference(self):
        source = transcript("If Bitcoin falls to support, it becomes interesting. I expect a bounce.")
        self.assertEqual(extract_bias(source).direction, "flat")

    def test_relative_pairs_and_implicit_threshold_conditions_abstain(self):
        for text in (
            "I am bullish on this one versus Bitcoin.",
            "Bitcoin is near support. That is where I start to turn bearish.",
            "That would put Bitcoin on new highs for this rally, I think.",
        ):
            with self.subTest(text=text):
                self.assertEqual(extract_bias(transcript(text)).direction, "flat")

    def test_long_single_clause_does_not_multiply_independent_support(self):
        source = transcript("I am bullish on Bitcoin and " + "we can inspect this carefully " * 12 +
                            "I expect Bitcoin to move higher.")
        self.assertEqual(extract_bias(source, "context_strict").direction, "flat")

    def test_bitcoin_context_cannot_be_carried_through_an_asset_switch(self):
        source = transcript("Bitcoin is on the screen.", "Ethereum is bullish right now.")
        self.assertEqual(extract_bias(source).direction, "flat")
        self.assertEqual(extract_bias(transcript("I am bullish right now.")).direction, "flat")

    def test_conflicting_current_views_cancel_without_outcome_selection(self):
        source = transcript("I am bullish on Bitcoin.", "I expect Bitcoin to move lower.")
        summary = extract_bias(source)
        self.assertEqual(summary.direction, "flat")
        self.assertEqual(summary.signed_score, 0)
        self.assertEqual((summary.positive_count, summary.negative_count), (1, 1))
        self.assertIn("conflicting_current_views", summary.issues)

    def test_repeated_words_in_one_claim_do_not_count_as_independent_support(self):
        source = transcript("I am bullish on Bitcoin and expect upside and higher prices.")
        self.assertEqual(extract_bias(source).supporting_count, 1)
        self.assertEqual(extract_bias(source, "context_strict").direction, "flat")

    def test_strict_variant_requires_two_distinct_supporting_claims(self):
        source = transcript("I am bullish on Bitcoin.", "I expect Bitcoin to move higher.")
        summary = extract_bias(source, "context_strict")
        self.assertEqual(summary.direction, "long")
        self.assertEqual(summary.supporting_count, 2)

    def test_lexical_baseline_exposes_the_expected_negation_failure(self):
        source = transcript("I am not bullish on Bitcoin.")
        self.assertEqual(extract_bias(source, "lexical").direction, "long")
        self.assertEqual(extract_bias(source, "context_standard").direction, "flat")

    def test_empty_and_unknown_configuration_are_explicit(self):
        summary = extract_bias(transcript("Bitcoin is trading near 100."))
        self.assertEqual((summary.video_id, summary.direction, summary.supporting_count),
                         ("synthetic-video", "flat", 0))
        with self.assertRaises(ValueError):
            extract_bias(transcript("I am bullish on Bitcoin."), "unregistered")
        self.assertEqual(set(BIAS_CONFIGS), {"lexical", "context_strict", "context_standard", "context_broad"})

    def test_independent_review_adversarial_examples_abstain(self):
        examples = (
            "I expected Bitcoin to go higher.",
            "When Bitcoin closes above 100, I am bullish.",
            "I am bullish on Bitcoin; only if the daily closes above 100.",
            "I am bullish on Bitcoin. Only if the daily closes above 100.",
            "Bob thinks Bitcoin is bullish.",
            "The viewer writes: I am bullish on Bitcoin.",
            "Many traders are bullish on Bitcoin.",
            "A viewer sent me a message about Bitcoin. I am bullish.",
            "I will be bullish on Bitcoin next month.",
            "I think Bitcoin could go higher.",
            "I am bullish on Bitcoin dominance.",
            "I am bullish on Bitcoin contingent on a daily close above 100.",
            "I am bullish on Bitcoin after it reclaims 100.",
            "Bitcoin is showing a bullish moving-average crossover.",
            "I am bullish on Cardano while Bitcoin is quiet.",
            "I am bullish on Unnamedcoin while Bitcoin is quiet.",
            "Yesterday I said this about Bitcoin. I am bullish.",
            "I am bullish on Bitcoin. Actually no, scratch that.",
            "Yesterday, " + "we can inspect this carefully " * 12 + "I am bullish on Bitcoin.",
            "I am not going to say " + "we can inspect this carefully " * 12 + "Bitcoin is bullish.",
        )
        for text in examples:
            for variant in ("context_strict", "context_standard", "context_broad"):
                with self.subTest(text=text, variant=variant):
                    self.assertEqual(extract_bias(transcript(text), variant).direction, "flat")

    def test_repeated_identical_captions_do_not_pass_strict_support_gate(self):
        source = transcript("I am bullish on Bitcoin. I am bullish on Bitcoin.")
        summary = extract_bias(source, "context_strict")
        self.assertEqual(summary.direction, "flat")
        self.assertEqual(summary.positive_count, 1)


class ProvenanceTests(unittest.TestCase):
    def test_exact_spans_preserve_source_timestamps_and_unicode(self):
        source = transcript("Bitcoin: I’m bullish", "right now, on this market.")
        [event] = extract_bias_events(source)
        self.assertEqual((event.start_seconds, event.end_seconds), (0, 20))
        self.assertEqual(event.video_id, source.source_id)
        for span in event.evidence:
            segment = next(segment for segment in source.segments if segment.id == span.segment_id)
            self.assertEqual(segment.text[span.char_start:span.char_end], span.quote)
            self.assertEqual((span.start_seconds, span.end_seconds), (segment.start, segment.end))
        validate_bias_grounding(event, source)
        span = event.evidence[0]
        with self.assertRaises(ValueError):
            validate_bias_grounding(replace(event, evidence=(replace(span, quote="not the source"),)), source)
        with self.assertRaises(ValueError):
            validate_bias_grounding(replace(event, video_id="another-video"), source)

    def test_chart_timeframe_and_forecast_horizon_have_different_roles(self):
        source = transcript("On the four hour chart, I am bullish on Bitcoin over the next 12 hours.")
        [event] = extract_bias_events(source)
        self.assertEqual(event.timeframe_minutes, 240)
        self.assertEqual(event.horizon_minutes, 720)
        self.assertFalse(hasattr(event, "expires_at"))

    def test_missing_horizon_and_instrument_stay_unspecified(self):
        [event] = extract_bias_events(transcript("I am bullish on Bitcoin right now."))
        self.assertIsNone(event.timeframe_minutes)
        self.assertIsNone(event.horizon_minutes)
        self.assertFalse(event.derivatives_mentioned)
        [future_event] = extract_bias_events(transcript("Bitcoin perpetual futures look bullish right now."))
        self.assertTrue(future_event.derivatives_mentioned)

    def test_decimal_chart_timeframe_is_not_misread_as_its_fractional_digit(self):
        [event] = extract_bias_events(transcript("On the 1.5 hour chart, I am bullish on Bitcoin."))
        self.assertIsNone(event.timeframe_minutes)

    def test_forged_direction_and_rule_weight_are_not_valid_grounding(self):
        source = transcript("I am bullish on Bitcoin.")
        [event] = extract_bias_events(source)
        for change in ({"direction": "short", "candidate_direction": "short"}, {"strength": 100}):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    validate_bias_grounding(replace(event, **change), source)

    def test_summary_quotes_are_bounded_but_full_internal_spans_remain_available(self):
        source = transcript("On the chart " + "we can inspect this carefully " * 12 +
                            "I am bullish on Bitcoin right now.")
        summary = extract_bias(source)
        self.assertLessEqual(sum(len(span.quote.split()) for span in summary.evidence), 25)
        for event in extract_bias_events(source):
            validate_bias_grounding(event, source)

    def test_summary_rejects_mixed_sources_and_variants(self):
        first = extract_bias_events(transcript("I am bullish on Bitcoin."))
        second = [replace(first[0], video_id="other-video")]
        with self.assertRaises(ValueError):
            aggregate_bias(first + second)
        with self.assertRaises(ValueError):
            aggregate_bias(first, "context_strict")


if __name__ == "__main__":
    unittest.main()
