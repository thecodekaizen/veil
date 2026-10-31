"""Tests for SHOWME's process graph boundary."""

import copy
import unittest

from showme.process import PROCESS_SCHEMA, validate_references


VALID_PROCESS = {
    "task_summary": "Move the red block onto the blue block.",
    "objects": [
        {"id": "red", "label": "red block", "visual_description": "small red cube"},
        {"id": "blue", "label": "blue block", "visual_description": "large blue cube"},
    ],
    "states": [
        {"id": "separate", "description": "Blocks are separate", "observable_facts": ["gap between blocks"]},
        {"id": "stacked", "description": "Red block rests on blue", "observable_facts": ["red above blue"]},
    ],
    "transitions": [{
        "id": "stack_blocks",
        "from_state": "separate",
        "action": "place red on blue",
        "object_ids": ["red", "blue"],
        "to_state": "stacked",
        "candidate_constraints": [],
        "postconditions": ["red above blue"],
        "evidence": [{"start_seconds": 0.5, "end_seconds": 1.0, "observation": "Red block visibly moves above blue."}],
        "reference_evidence": [],
    }],
    "ordering_observations": [],
    "uncertainties": [],
}


class ProcessValidationTests(unittest.TestCase):
    def test_process_schema_labels_model_constraints_as_unverified_candidates(self):
        transition = PROCESS_SCHEMA["properties"]["transitions"]["items"]
        self.assertIn("candidate_constraints", transition["properties"])
        self.assertNotIn("preconditions", transition["properties"])
        self.assertIn("Unverified model hypotheses", transition["properties"]["candidate_constraints"]["description"])
        self.assertIn("reference_evidence", transition["properties"])

    def test_accepts_well_formed_references(self):
        validate_references(copy.deepcopy(VALID_PROCESS))

    def test_rejects_unknown_from_state(self):
        process = copy.deepcopy(VALID_PROCESS)
        process["transitions"][0]["from_state"] = "missing"
        with self.assertRaisesRegex(ValueError, "unknown from_state"):
            validate_references(process)

    def test_rejects_unknown_to_state(self):
        process = copy.deepcopy(VALID_PROCESS)
        process["transitions"][0]["to_state"] = "missing"
        with self.assertRaisesRegex(ValueError, "unknown to_state"):
            validate_references(process)

    def test_rejects_unknown_object(self):
        process = copy.deepcopy(VALID_PROCESS)
        process["transitions"][0]["object_ids"] = ["missing"]
        with self.assertRaisesRegex(ValueError, "unknown object_id"):
            validate_references(process)

    def test_rejects_duplicate_state_ids(self):
        process = copy.deepcopy(VALID_PROCESS)
        process["states"].append(copy.deepcopy(process["states"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate state id"):
            validate_references(process)

    def test_rejects_duplicate_transition_ids(self):
        process = copy.deepcopy(VALID_PROCESS)
        process["transitions"].append(copy.deepcopy(process["transitions"][0]))
        with self.assertRaisesRegex(ValueError, "duplicate transition id"):
            validate_references(process)

    def test_rejects_ordering_observation_with_unknown_transition(self):
        process = copy.deepcopy(VALID_PROCESS)
        process["ordering_observations"] = [{
            "before_transition_id": "missing",
            "after_transition_id": "stack_blocks",
            "evidence": [{"start_seconds": 0, "end_seconds": 1, "observation": "Visible order."}],
        }]
        with self.assertRaisesRegex(ValueError, "unknown before_transition_id"):
            validate_references(process)

    def test_accepts_evidence_backed_observed_order(self):
        process = copy.deepcopy(VALID_PROCESS)
        process["transitions"].append({
            "id": "separate_blocks",
            "from_state": "separate",
            "action": "move red beside blue",
            "object_ids": ["red", "blue"],
            "to_state": "separate",
            "candidate_constraints": [],
            "postconditions": [],
            "evidence": [{"start_seconds": 0.1, "end_seconds": 0.3, "observation": "Red is placed beside blue."}],
            "reference_evidence": [],
        })
        process["ordering_observations"] = [{
            "before_transition_id": "separate_blocks",
            "after_transition_id": "stack_blocks",
            "evidence": [{"start_seconds": 0.1, "end_seconds": 1.0, "observation": "The side-by-side arrangement occurs before stacking."}],
        }]
        validate_references(process)

    def test_rejects_evidence_interval_beyond_expert_clip(self):
        process = copy.deepcopy(VALID_PROCESS)
        with self.assertRaisesRegex(ValueError, "outside the expert clip"):
            validate_references(process, duration_seconds=0.75)

    def test_rejects_transitions_without_visual_evidence(self):
        process = copy.deepcopy(VALID_PROCESS)
        process["transitions"][0]["evidence"] = []
        with self.assertRaisesRegex(ValueError, "needs video or reference evidence"):
            validate_references(process)

    def test_accepts_a_reference_only_transition_with_a_page_and_step_citation(self):
        process = copy.deepcopy(VALID_PROCESS)
        transition = process["transitions"][0]
        transition["evidence"] = []
        transition["reference_evidence"] = [{"page": 2, "step": "17", "observation": "The diagram shows the left wing attached to the body."}]
        validate_references(process)

    def test_rejects_reference_only_transition_without_a_source_citation(self):
        process = copy.deepcopy(VALID_PROCESS)
        transition = process["transitions"][0]
        transition["evidence"] = []
        transition["reference_evidence"] = [{"page": 0, "step": "", "observation": ""}]
        with self.assertRaisesRegex(ValueError, "page must be a positive integer"):
            validate_references(process)

    def test_rejects_transition_without_video_or_manual_evidence(self):
        process = copy.deepcopy(VALID_PROCESS)
        process["transitions"][0]["evidence"] = []
        with self.assertRaisesRegex(ValueError, "needs video or reference evidence"):
            validate_references(process)


if __name__ == "__main__":
    unittest.main()
