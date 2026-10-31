"""Tests for local, label-only HoloAssist event-time scoring."""

import unittest

from showme.evaluation import score_holoassist_observation


def make_annotation():
    return {
        "video_name": "R005-demo",
        "video_duration": {"seconds": 30},
        "actions": [{"fine_grained_actions": [
            {"start_time": 10, "end_time": 12, "fine_grained_action_attributes": {"Action Correctness": "Wrong Action, corrected by student"}},
            {"start_time": 20, "end_time": 21, "fine_grained_action_attributes": {"Action Correctness": "Correct Action"}},
        ]}],
    }


class HoloAssistScoringTests(unittest.TestCase):
    def test_exact_interval_match_and_miss_are_counted(self):
        result = score_holoassist_observation(
            {"divergences": [{"time_seconds": 11}, {"time_seconds": 25}]},
            make_annotation(),
        )
        self.assertEqual(result["counts"], {
            "true_positive": 1,
            "false_positive": 1,
            "false_negative": 0,
            "predictions": 2,
            "labeled_wrong_actions": 1,
        })
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["recall"], 1.0)
        self.assertEqual(result["f1"], 2 / 3)

    def test_optional_tolerance_extends_the_annotation_interval(self):
        result = score_holoassist_observation(
            {"divergences": [{"time_seconds": 12.5}]},
            make_annotation(),
            tolerance_seconds=0.5,
        )
        self.assertEqual(result["counts"]["true_positive"], 1)

    def test_only_one_prediction_can_match_each_labeled_interval(self):
        result = score_holoassist_observation(
            {"divergences": [{"time_seconds": 10.5}, {"time_seconds": 11.5}]},
            make_annotation(),
        )
        self.assertEqual(result["counts"]["true_positive"], 1)
        self.assertEqual(result["counts"]["false_positive"], 1)

    def test_overlapping_intervals_use_maximum_one_to_one_matching(self):
        annotation = make_annotation()
        annotation["actions"][0]["fine_grained_actions"] = [
            {"start_time": 10, "end_time": 20, "fine_grained_action_attributes": {"Action Correctness": "Wrong Action"}},
            {"start_time": 10, "end_time": 12, "fine_grained_action_attributes": {"Action Correctness": "Wrong Action"}},
        ]
        result = score_holoassist_observation(
            {"divergences": [{"time_seconds": 11}, {"time_seconds": 18}]},
            annotation,
        )
        self.assertEqual(result["counts"]["true_positive"], 2)
        self.assertEqual(result["counts"]["false_negative"], 0)

    def test_rejects_non_finite_and_out_of_clip_timestamps(self):
        for timestamp in (float("nan"), -1, 30):
            with self.subTest(timestamp=timestamp), self.assertRaises(ValueError):
                score_holoassist_observation(
                    {"divergences": [{"time_seconds": timestamp}]},
                    make_annotation(),
                )

    def test_rejects_negative_tolerance(self):
        with self.assertRaisesRegex(ValueError, "non-negative"):
            score_holoassist_observation({"divergences": []}, make_annotation(), tolerance_seconds=-1)


if __name__ == "__main__":
    unittest.main()
