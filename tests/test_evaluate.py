"""Analytic calibration fixtures; none are trading performance observations."""
from copy import deepcopy
import math
import unittest

from signal_lab.evaluate import calibration_report


def row(probabilities=None, label="buy", **changes):
    return {"probabilities": {"buy": .8, "sell": .1, "hold": .1} if probabilities is None else probabilities,
            "label": label, "predicted_at": "2026-01-01T10:00:00Z",
            "observed_at": "2026-01-01T11:00:00Z", **changes}


class CalibrationReportTests(unittest.TestCase):
    def test_known_multiclass_brier_ece_and_coverage_arithmetic(self):
        rows = [row(), row({"buy": .6, "sell": .3, "hold": .1}, "sell", abstained=True)]
        result = calibration_report(rows, bins=1)
        # (.06 + .86) / 2; all-label accuracy 1/2; mean confidence .7.
        self.assertAlmostEqual(result["brier_multiclass_sum"], .46)
        self.assertAlmostEqual(result["accuracy"], .5)
        self.assertAlmostEqual(result["ece"], .2)
        self.assertAlmostEqual(result["coverage"], .5)
        self.assertEqual(result["task"], "rule_decision_classification")
        self.assertIn("no estimate", result["limitation"])

    def test_separate_confidence_bins_change_ece_as_expected(self):
        rows = [row(), row({"buy": .6, "sell": .3, "hold": .1}, "sell")]
        result = calibration_report(rows, bins=10)
        self.assertAlmostEqual(result["ece"], .4)
        self.assertEqual(sum(bucket["count"] for bucket in result["buckets"]), 2)

    def test_perfect_confidence_one_is_included_in_last_bin(self):
        result = calibration_report([row({"buy": 1.0, "sell": 0.0, "hold": 0.0})])
        self.assertEqual(result["accuracy"], 1)
        self.assertEqual(result["brier_multiclass_sum"], 0)
        self.assertEqual(result["ece"], 0)
        self.assertEqual(result["buckets"][0]["upper"], 1)
        self.assertEqual(result["buckets"][0]["count"], 1)

    def test_confidently_wrong_prediction_has_multiclass_brier_two(self):
        result = calibration_report([row({"buy": 1.0, "sell": 0.0, "hold": 0.0}, "hold")])
        self.assertEqual(result["accuracy"], 0)
        self.assertEqual(result["brier_multiclass_sum"], 2)
        self.assertEqual(result["ece"], 1)

    def test_all_abstained_means_zero_coverage_not_zero_classification_accuracy(self):
        result = calibration_report([row(abstained=True)])
        self.assertEqual(result["coverage"], 0)
        self.assertEqual(result["accuracy"], 1)

    def test_nan_inf_booleans_negative_out_of_range_and_bad_sums_reject(self):
        for probs in ({"buy": math.nan, "sell": .1, "hold": .1},
                      {"buy": math.inf, "sell": .1, "hold": .1},
                      {"buy": True, "sell": 0, "hold": 0},
                      {"buy": -.1, "sell": .6, "hold": .5},
                      {"buy": 1.1, "sell": 0, "hold": 0},
                      {"buy": .5, "sell": .1, "hold": .1},
                      {"buy": "0.8", "sell": .1, "hold": .1}):
            with self.subTest(probs=probs), self.assertRaises(ValueError):
                calibration_report([row(probs)])

    def test_unknown_labels_or_missing_probability_classes_reject(self):
        for item in (row(label="long"), row({}), row({"buy": 1}),
                     row({"buy": .8, "sell": .1, "hold": .1, "other": 0})):
            with self.subTest(item=item), self.assertRaises(ValueError):
                calibration_report([item])

    def test_outcome_before_prediction_and_naive_times_reject(self):
        for changes in ({"observed_at": "2026-01-01T09:59:59Z"},
                        {"predicted_at": "2026-01-01T10:00:00"},
                        {"observed_at": "not-a-timestamp"}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                calibration_report([row(**changes)])

    def test_timezone_offsets_are_compared_as_instants(self):
        result = calibration_report([row(predicted_at="2026-01-01T11:00:00+01:00",
                                         observed_at="2026-01-01T10:00:00Z")])
        self.assertEqual(result["rows"], 1)

    def test_invalid_bins_empty_rows_and_nonboolean_abstention_reject(self):
        for bins in (0, -1, 101, True, 1.5):
            with self.subTest(bins=bins), self.assertRaises(ValueError):
                calibration_report([row()], bins=bins)
        with self.assertRaises(ValueError):
            calibration_report([])
        for abstained in ("false", 1, None):
            with self.subTest(abstained=abstained), self.assertRaises(ValueError):
                calibration_report([row(abstained=abstained)])

    def test_missing_and_nonobject_rows_raise_validation_errors(self):
        for malformed in ({}, None, "row", [], {"label": "buy"}):
            with self.subTest(malformed=malformed), self.assertRaises(ValueError):
                calibration_report([malformed])

    def test_report_does_not_mutate_input_rows(self):
        rows = [row()]
        original = deepcopy(rows)
        calibration_report(rows)
        self.assertEqual(rows, original)

    def test_ties_have_stable_results_independent_of_json_key_order(self):
        a = row({"buy": .5, "sell": .5, "hold": 0}, "buy")
        b = row({"sell": .5, "buy": .5, "hold": 0}, "buy")
        self.assertEqual(calibration_report([a])["accuracy"], calibration_report([b])["accuracy"])


if __name__ == "__main__":
    unittest.main()
