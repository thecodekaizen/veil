import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from thermal_investigator.contracts import experiment_library, initial_schedule
from thermal_investigator.decisions import public_context, validate_decision
from thermal_investigator.design import design_scores
from thermal_investigator.lab import Lab
from thermal_investigator.meta import MetaDecider
from thermal_investigator.predictor import Predictor, fit_candidates, select_model


class DecisionTests(unittest.TestCase):
    def setUp(self):
        self.obs = Lab(11, False).run(initial_schedule().to_dict())
        self.candidates = fit_candidates([self.obs])
        self.plans = experiment_library()
        self.context = public_context([self.obs], self.candidates, self.plans)
        self.decision = {"schedule_id": self.plans[0].id, "model_order": self.candidates[0].order,
                         "rationale": "Excite one heater independently of the other.",
                         "evidence_ids": [self.obs["observation_id"]], "uncertainty": "provisional"}

    def test_information_design_prefers_new_input_excitation(self):
        choices = [initial_schedule(), self.plans[0]]
        rows = design_scores(self.candidates, [self.obs], choices)
        self.assertGreater(rows[1]["d_optimal_gain_per_parameter"], rows[0]["d_optimal_gain_per_parameter"])
        self.assertTrue(all(np.isfinite(r["d_optimal_gain_per_parameter"]) for r in rows))

    def test_hidden_fields_cannot_enter_context_through_observation(self):
        contaminated = {**self.obs, "seed": 11, "world": "secret", "answer_key": {"sensor_tau": 9}}
        context = public_context([contaminated], self.candidates, self.plans)
        encoded = json.dumps(context)
        self.assertNotIn('"seed"', encoded)
        self.assertNotIn('"world"', encoded)
        self.assertNotIn('"answer_key"', encoded)
        self.assertNotIn('"sensor_tau"', encoded)

    def test_unknown_experiment_model_or_evidence_is_rejected(self):
        for key, value in (("schedule_id", "not-available"), ("model_order", 99),
                           ("model_order", True), ("evidence_ids", ["unseen"]), ("evidence_ids", [])):
            with self.assertRaises(ValueError):
                validate_decision({**self.decision, key: value}, self.context)
        with self.assertRaises(ValueError):
            validate_decision({**self.decision, "future_temperature": [25]}, self.context)

    def test_validated_model_precedes_unvalidated_lower_training_error(self):
        valid = Predictor(1, .1, np.zeros((4, 2)), .2, 2.0, .5, "whole_trial_leave_one_out")
        unknown = Predictor(2, .1, np.zeros((8, 2)), .001, None, .5)
        self.assertIs(select_model([unknown, valid]), valid)

    def response(self, decision):
        return {"status": "completed", "usage": {"input_tokens": 200, "output_tokens": 100},
                "output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(decision)}]}]}

    def test_valid_response_is_cached_and_credentials_never_saved(self):
        calls = []
        def transport(payload):
            calls.append(payload)
            return self.response(self.decision)
        with tempfile.TemporaryDirectory() as folder:
            provider = MetaDecider("test-secret-only", Path(folder), max_calls=1, transport=transport)
            _, first = provider.decide(self.context, "meta_direct")
            _, second = provider.decide(self.context, "meta_direct")
            self.assertFalse(first["cache_hit"])
            self.assertTrue(second["cache_hit"])
            self.assertEqual(len(calls), 1)
            contents = "".join(p.read_text() for p in Path(folder).glob("*.json"))
            self.assertNotIn("test-secret-only", contents)

    def test_invalid_response_has_no_retry_and_still_counts_usage(self):
        calls = []
        def transport(payload):
            calls.append(payload)
            return self.response({**self.decision, "model_order": 99})
        with tempfile.TemporaryDirectory() as folder:
            provider = MetaDecider("test-key", Path(folder), max_calls=1, transport=transport)
            for _ in range(2):
                with self.assertRaises(ValueError):
                    provider.decide(self.context, "meta_direct")
            self.assertEqual(len(calls), 1)
            state = json.loads((Path(folder) / "usage-state.json").read_text())
            self.assertEqual(state["attempts"], 1)
            self.assertGreater(state["charged_or_reserved_usd"], 0)

    def test_cost_guard_blocks_before_transport(self):
        calls = []
        with tempfile.TemporaryDirectory() as folder:
            provider = MetaDecider("test-key", Path(folder), budget_usd=.000001,
                                   transport=lambda body: calls.append(body))
            with self.assertRaisesRegex(ValueError, "guard exhausted"):
                provider.decide(self.context, "meta_direct")
            self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
