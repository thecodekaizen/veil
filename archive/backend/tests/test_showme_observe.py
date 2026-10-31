"""Tests for evidence and state checks on learner observations."""

import copy
import unittest

from showme.observe import (
    observation_prompt,
    observation_schema,
    snapshot_prompt,
    snapshot_schema,
    validate_observation,
    validate_snapshot,
)
from test_showme_process import VALID_PROCESS


class ObservationValidationTests(unittest.TestCase):
    def setUp(self):
        self.process = copy.deepcopy(VALID_PROCESS)
        self.valid = {
            "events": [
                {"time_seconds": 1.0, "action": "start", "state_id": "separate", "assessment": "consistent", "object_ids": ["red", "blue"], "evidence": "The blocks are apart."},
                {"time_seconds": 4.0, "action": "stack", "state_id": "stacked", "assessment": "consistent", "object_ids": ["red", "blue"], "evidence": "Red rests on blue."},
            ],
            "divergences": [],
            "recovery_status": "no_divergence_observed",
            "uncertainties": [],
            "reference_checks": [],
        }

    def test_observer_retains_transient_interactions_without_assuming_error(self):
        prompt = observation_prompt(self.process, 5)
        self.assertIn("Do not omit an observed interaction", prompt)
        self.assertIn("not automatically a procedural error", prompt)
        self.assertIn("unclear event with state_id unknown", prompt)

    def test_accepts_grounded_valid_timeline(self):
        validate_observation(self.valid, self.process, 5.0)

    def test_rejects_unknown_state(self):
        output = copy.deepcopy(self.valid)
        output["events"][0]["state_id"] = "invented"
        with self.assertRaisesRegex(ValueError, "unknown state_id"):
            validate_observation(output, self.process, 5.0)

    def test_rejects_timestamp_outside_clip(self):
        output = copy.deepcopy(self.valid)
        output["events"][1]["time_seconds"] = 5.0
        with self.assertRaisesRegex(ValueError, "within the clip"):
            validate_observation(output, self.process, 5.0)

    def test_rejects_out_of_order_events(self):
        output = copy.deepcopy(self.valid)
        output["events"].reverse()
        with self.assertRaisesRegex(ValueError, "chronological"):
            validate_observation(output, self.process, 5.0)

    def test_recovered_requires_divergence_and_later_consistent_state(self):
        output = copy.deepcopy(self.valid)
        output["recovery_status"] = "recovered"
        with self.assertRaisesRegex(ValueError, "without a visible divergence"):
            validate_observation(output, self.process, 5.0)

    def test_divergent_event_requires_a_divergence_record(self):
        output = copy.deepcopy(self.valid)
        output["events"][0]["assessment"] = "divergent"
        with self.assertRaisesRegex(ValueError, "divergent events need at least one divergence record"):
            validate_observation(output, self.process, 5.0)

    def test_no_divergence_status_cannot_hide_a_divergent_event(self):
        output = copy.deepcopy(self.valid)
        output["events"][0]["assessment"] = "divergent"
        output["divergences"] = [{
            "time_seconds": 1.0,
            "process_difference": "red block is beside rather than above blue",
            "object_ids": ["red", "blue"],
            "evidence": "At 1.0s the blocks are side by side.",
        }]
        with self.assertRaisesRegex(ValueError, "recovery status conflicts"):
            validate_observation(output, self.process, 5.0)

    def test_accepts_recovery_only_after_later_consistent_state(self):
        output = copy.deepcopy(self.valid)
        output["events"][0]["assessment"] = "divergent"
        output["divergences"] = [{
            "time_seconds": 1.5,
            "process_difference": "red block is beside rather than above blue",
            "object_ids": ["red", "blue"],
            "evidence": "At 1.5s the blocks are side by side.",
        }]
        output["recovery_status"] = "recovered"
        validate_observation(output, self.process, 5.0)

    def test_rejects_recovery_without_later_consistent_event(self):
        output = copy.deepcopy(self.valid)
        output["events"][0]["assessment"] = "divergent"
        output["events"][1]["assessment"] = "divergent"
        output["divergences"] = [{
            "time_seconds": 1.5,
            "process_difference": "unexpected arrangement",
            "object_ids": ["red"],
            "evidence": "Visible at 1.5s.",
        }]
        output["recovery_status"] = "recovered"
        with self.assertRaisesRegex(ValueError, "later process-consistent"):
            validate_observation(output, self.process, 5.0)

    def recovery_report(self):
        output = copy.deepcopy(self.valid)
        output["events"][0]["assessment"] = "divergent"
        output["divergences"] = [{"time_seconds": 1.0, "object_ids": ["red"], "evidence": "Red is misplaced."}]
        output["recovery_status"] = "recovered"
        return output

    def test_rejects_recovery_from_unrelated_object_progress(self):
        output = self.recovery_report()
        output["events"][1]["object_ids"] = ["blue"]
        with self.assertRaisesRegex(ValueError, "each affected object"):
            validate_observation(output, self.process, 5.0)

    def test_rejects_recovery_before_a_later_difference(self):
        output = self.recovery_report()
        output["divergences"].append({"time_seconds": 4.5, "object_ids": ["red"], "evidence": "Red is misplaced again."})
        with self.assertRaisesRegex(ValueError, "after the last divergence"):
            validate_observation(output, self.process, 5.0)

    def test_rejects_recovery_before_later_divergent_event(self):
        output = self.recovery_report()
        output["events"].append({**output["events"][0], "time_seconds": 4.5})
        with self.assertRaisesRegex(ValueError, "after the last divergence"):
            validate_observation(output, self.process, 5.0)

    def test_rejects_recovery_when_affected_object_is_unknown(self):
        output = self.recovery_report()
        output["divergences"][0]["object_ids"] = ["unknown"]
        with self.assertRaisesRegex(ValueError, "each affected object"):
            validate_observation(output, self.process, 5.0)

    def test_recovery_requires_all_reported_differences_to_be_covered(self):
        output = self.recovery_report()
        output["divergences"].append({"time_seconds": 1.5, "object_ids": ["blue"], "evidence": "Blue is also misplaced."})
        output["events"][1]["object_ids"] = ["red"]
        with self.assertRaisesRegex(ValueError, "each affected object"):
            validate_observation(output, self.process, 5.0)
        output["events"].append({**output["events"][1], "time_seconds": 4.5, "object_ids": ["blue"]})
        validate_observation(output, self.process, 5.0)

    def test_observation_schema_limits_model_to_declared_ids(self):
        schema = observation_schema(self.process)
        state_enum = schema["properties"]["events"]["items"]["properties"]["state_id"]["enum"]
        self.assertEqual(state_enum, ["separate", "stacked", "unknown"])

    def test_reference_check_schema_limits_to_cited_transitions(self):
        self.process["transitions"][0]["reference_evidence"] = [{"page": 1, "step": "1", "observation": "Place red on blue."}]
        schema = observation_schema(self.process)
        transition_enum = schema["properties"]["reference_checks"]["items"]["properties"]["transition_id"]["enum"]
        self.assertEqual(transition_enum, [self.process["transitions"][0]["id"]])

    def test_prompt_does_not_include_run_metadata(self):
        self.process["_run"] = {"remote_file_id": "secret-file-id", "model": "muse-spark-1.3"}
        prompt = observation_prompt(self.process, 12.0)
        self.assertNotIn("secret-file-id", prompt)
        self.assertIn("may be correct, divergent", prompt)

    def test_prompt_does_not_treat_demo_order_as_a_requirement(self):
        prompt = observation_prompt(self.process, 12.0)
        self.assertIn("not required prerequisites", prompt)
        self.assertIn("not call a learner divergent only because", prompt)

    def test_reference_transitions_require_one_check_each(self):
        self.process["transitions"][0]["reference_evidence"] = [{"page": 1, "step": "1", "observation": "Place red on blue."}]
        with self.assertRaisesRegex(ValueError, "each reference transition exactly once"):
            validate_observation(self.valid, self.process, 5.0)

    def test_accepts_not_shown_reference_step_with_guidance(self):
        self.process["transitions"][0]["reference_evidence"] = [{"page": 1, "step": "1", "observation": "Place red on blue."}]
        output = copy.deepcopy(self.valid)
        output["reference_checks"] = [{
            "transition_id": self.process["transitions"][0]["id"],
            "status": "not_shown",
            "time_seconds": None,
            "evidence": "The clip begins after the blocks are already arranged.",
            "next_guidance": "Show the starting pieces, then place the red block on the blue block.",
        }]
        validate_observation(output, self.process, 5.0)

    def test_rejects_duplicate_reference_checks(self):
        self.process["transitions"][0]["reference_evidence"] = [{"page": 1, "step": "1", "observation": "Place red on blue."}]
        check = {"transition_id": self.process["transitions"][0]["id"], "status": "unclear", "time_seconds": 1.0, "evidence": "Hands cover the joint.", "next_guidance": "Move your hand and show the joint."}
        output = copy.deepcopy(self.valid)
        output["reference_checks"] = [check, copy.deepcopy(check)]
        with self.assertRaisesRegex(ValueError, "exactly once"):
            validate_observation(output, self.process, 5.0)

    def test_rejects_mismatch_without_divergence(self):
        self.process["transitions"][0]["reference_evidence"] = [{"page": 1, "step": "1", "observation": "Place red on blue."}]
        output = copy.deepcopy(self.valid)
        output["reference_checks"] = [{"transition_id": self.process["transitions"][0]["id"], "status": "possible_mismatch", "time_seconds": 1.0, "evidence": "Red is beside blue.", "next_guidance": "Place red on top of blue."}]
        with self.assertRaisesRegex(ValueError, "at the same evidence time"):
            validate_observation(output, self.process, 5.0)

    def test_rejects_unshown_reference_step_with_timestamp(self):
        self.process["transitions"][0]["reference_evidence"] = [{"page": 1, "step": "1", "observation": "Place red on blue."}]
        output = copy.deepcopy(self.valid)
        output["reference_checks"] = [{"transition_id": self.process["transitions"][0]["id"], "status": "not_shown", "time_seconds": 1.0, "evidence": "The step is not in the clip.", "next_guidance": "Show the step."}]
        with self.assertRaisesRegex(ValueError, "null timestamp"):
            validate_observation(output, self.process, 5.0)


class SnapshotValidationTests(unittest.TestCase):
    def setUp(self):
        self.process = copy.deepcopy(VALID_PROCESS)
        self.valid = {
            "state_id": "stacked",
            "assessment": "consistent",
            "object_ids": ["red", "blue"],
            "evidence": "The red block is visibly resting on the blue block.",
            "uncertainties": [],
            "view_guidance": "",
        }

    def test_accepts_declared_consistent_state(self):
        validate_snapshot(self.valid, self.process)

    def test_rejects_unknown_ids(self):
        output = copy.deepcopy(self.valid)
        output["state_id"] = "invented"
        with self.assertRaisesRegex(ValueError, "unknown state_id"):
            validate_snapshot(output, self.process)

    def test_rejects_consistent_without_a_known_state(self):
        output = copy.deepcopy(self.valid)
        output["state_id"] = "unknown"
        with self.assertRaisesRegex(ValueError, "must match a declared state"):
            validate_snapshot(output, self.process)

    def test_schema_limits_states_and_objects_to_reviewed_process(self):
        schema = snapshot_schema(self.process)
        self.assertEqual(schema["properties"]["state_id"]["enum"], ["separate", "stacked", "unknown"])
        self.assertEqual(schema["properties"]["object_ids"]["items"]["enum"], ["red", "blue", "unknown"])

    def test_prompt_does_not_infer_recovery_or_require_observed_order(self):
        prompt = snapshot_prompt(self.process)
        self.assertIn("do not infer action order", prompt)
        self.assertIn("do not infer", prompt)
        self.assertIn("recovery", prompt)

    def test_unclear_snapshot_requires_actionable_view_guidance(self):
        output = copy.deepcopy(self.valid)
        output.update({"assessment": "unclear", "state_id": "unknown", "view_guidance": "Move your hand away and show the joint from above."})
        validate_snapshot(output, self.process)
        output["view_guidance"] = ""
        with self.assertRaisesRegex(ValueError, "need actionable view_guidance"):
            validate_snapshot(output, self.process)


if __name__ == "__main__":
    unittest.main()
