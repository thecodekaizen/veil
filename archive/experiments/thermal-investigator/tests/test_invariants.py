import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from thermal_investigator.contracts import Schedule, Segment, experiment_library, initial_schedule
from thermal_investigator.lab import Lab, challenge_commands, parameters, trajectory
from thermal_investigator.predictor import fit_candidates, select_model
from thermal_investigator.run import LabClient, run_case


class ContractTests(unittest.TestCase):
    def test_nan_and_out_of_envelope_commands_rejected(self):
        for value in (float("nan"), float("inf"), -1., 66.):
            with self.assertRaises(ValueError):
                Schedule("invalid", (Segment(120., value, 0.),)).commands()

    def test_duration_and_resolution_enforced(self):
        for seconds in (0., -2., 119., 121., 122.):
            with self.assertRaises(ValueError):
                Schedule("bad", (Segment(seconds, 0., 0.),)).commands()

    def test_malformed_attempt_consumes_a_slot(self):
        lab = Lab(11, False, max_actions=1)
        with self.assertRaises(ValueError):
            lab.run({"id": "invalid", "segments": []})
        with self.assertRaisesRegex(ValueError, "budget exhausted"):
            lab.run(initial_schedule().to_dict())

    def test_public_observations_exclude_world_parameters(self):
        a = Lab(11, False).run(initial_schedule().to_dict())
        b = Lab(11, False).run(initial_schedule().to_dict())
        self.assertEqual(a["temperature_c"], b["temperature_c"])
        self.assertNotEqual(a["session_id"], b["session_id"])
        for key in ("seed", "world", "parameters", "sensor_tau", "clean_temperature_c"):
            self.assertNotIn(key, a)

    def test_paired_measurement_noise_does_not_depend_on_action_order(self):
        a, b = Lab(11, True), Lab(11, True)
        a.run(initial_schedule().to_dict())
        plan = experiment_library()[0].to_dict()
        self.assertEqual(a.run(plan)["temperature_c"], b.run(plan)["temperature_c"])

    def test_challenge_is_revealed_once_and_shape_checked(self):
        lab = Lab(11, False)
        with self.assertRaises(ValueError):
            lab.challenge({"temperature_c": [[22., 22.]]})
        predicted = trajectory(challenge_commands(), parameters(11, False))
        result = lab.challenge({"temperature_c": predicted.tolist()})
        self.assertAlmostEqual(result["mean_rmse_c"], 0.)
        with self.assertRaisesRegex(ValueError, "Investigation closed"):
            lab.run(initial_schedule().to_dict())
        with self.assertRaisesRegex(ValueError, "already revealed"):
            lab.challenge({"temperature_c": predicted.tolist()})


class NumericalTests(unittest.TestCase):
    def test_integrator_convergence_and_no_input_equilibrium(self):
        p = parameters(23, True)
        commands = np.asarray(experiment_library()[2].commands())
        coarse = trajectory(commands, p, step=.25)
        fine = trajectory(commands, p, step=.125)
        self.assertLess(float(np.max(np.abs(coarse - fine))), 1e-5)
        self.assertTrue(np.all(coarse >= 22.))
        self.assertTrue(np.all(trajectory(np.zeros((60, 2)), p) == 22.))

    def test_fitter_can_predict_an_unseen_input_without_simulator_parameters(self):
        lab = Lab(23, False)
        observations = [lab.run(plan.to_dict()) for plan in [initial_schedule()] + experiment_library()[:3]]
        model = select_model(fit_candidates(observations))
        result = lab.challenge({"temperature_c": model.predict(challenge_commands()).tolist()})
        self.assertLess(result["mean_rmse_c"], .3)
        self.assertEqual(model.validation_status, "whole_trial_leave_one_out")

    def test_stable_full_fit_can_remain_provisional_when_cv_fold_fails(self):
        lab = Lab(11, True)
        observations = [lab.run(initial_schedule().to_dict()), lab.run(experiment_library()[5].to_dict())]
        candidates = fit_candidates(observations)
        self.assertTrue(candidates)
        self.assertTrue(all(c.spectral_radius < 1. for c in candidates))
        for model in candidates:
            if model.validation_status == "incomplete_unstable_reduced_fit":
                self.assertIsNone(model.validation_rmse_c)

    def test_protocol_process_returns_generic_errors_and_keeps_running(self):
        client = LabClient(11, False, 1)
        try:
            with self.assertRaises(ValueError):
                client.request({"operation": "experiment", "schedule": {"id": "bad", "segments": []}})
            inputs = client.request({"operation": "challenge_inputs"})
            self.assertEqual(len(inputs["commands_fraction"]), 60)
        finally:
            client.close()

    def test_prediction_commit_precedes_reveal_and_is_exported(self):
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "case"
            result = run_case(output, 23, False, "fixed", 2)
            self.assertNotEqual(result.get("status"), "failed", result)
            events = [json.loads(line) for line in (output / "events.jsonl").read_text().splitlines()]
            kinds = [row["kind"] for row in events]
            self.assertLess(kinds.index("prediction_committed"), kinds.index("challenge_revealed"))
            self.assertTrue((output / "prediction-commit.json").exists())
            self.assertEqual(result["meta_calls"], 0)
            self.assertEqual(result["action_count"], 3)
            self.assertEqual(result["experimental_time_s"], 3 * (120 + 300))


if __name__ == "__main__":
    unittest.main()
