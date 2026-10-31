import importlib.util
import unittest

if importlib.util.find_spec("scipy") is None:
    raise unittest.SkipTest("Install the optional science dependencies to run physical-model checks")

import numpy as np

from thermal_investigator.contracts import experiment_library, initial_schedule
from thermal_investigator.lab import Lab, parameters, trajectory
from thermal_investigator.physical import ThermalSpec, execute_model, fit_physical, simulate


class PhysicalModelTests(unittest.TestCase):
    def test_exported_spec_round_trips(self):
        for lag in (False, True):
            spec = ThermalSpec(lag)
            self.assertEqual(ThermalSpec.from_dict(spec.to_dict()), spec)

    def test_unknown_structure_and_code_are_rejected(self):
        for value in ({"type": "arbitrary", "sensor_lag": False},
                      {"type": "two_node_thermal", "sensor_lag": 1},
                      {"type": "two_node_thermal", "sensor_lag": False, "code": "print(1)"}):
            with self.assertRaises(ValueError):
                ThermalSpec.from_dict(value)

    def test_exact_step_solution_matches_independent_rk4_simulator(self):
        for lag in (False, True):
            p = parameters(23, lag)
            rates = [p.loss1/p.c1, p.loss2/p.c2, p.coupling/p.c1,
                     p.coupling/p.c2, p.heater1_w/p.c1, p.heater2_w/p.c2]
            if lag:
                rates += [p.sensor_tau]
            inputs = experiment_library()[2].commands()
            exact = simulate(ThermalSpec(lag), rates, inputs)
            numerical = trajectory(np.asarray(inputs), p)
            self.assertLess(float(np.max(np.abs(exact-numerical))), 1e-5)

    def test_positive_loss_dynamics_cool_toward_ambient(self):
        rates = [.01, .01, .005, .005, .3, .2]
        commands = [[.6, 0.]]*30+[[0., 0.]]*1000
        predicted = simulate(ThermalSpec(False), rates, commands)
        self.assertGreater(predicted[30, 0], 22.)
        self.assertLess(abs(predicted[-1, 0]-22.), .001)
        self.assertTrue(np.all(predicted >= 22.-1e-12))

    def test_negative_rates_nan_and_excessive_power_rejected(self):
        rates = np.array([.01, .01, .005, .005, .3, .2])
        for index, value in ((0, -.01), (1, float("nan"))):
            bad = rates.copy()
            bad[index] = value
            with self.assertRaises(ValueError):
                simulate(ThermalSpec(False), bad, [[.5, 0.]])
        with self.assertRaises(ValueError):
            simulate(ThermalSpec(False), rates, [[1., 0.]])

    def test_fit_uses_observations_and_exports_an_executable_predictor(self):
        lab = Lab(23, True, 3)
        observations = [lab.run(p.to_dict()) for p in [initial_schedule()]+experiment_library()[:2]]
        fitted = fit_physical(observations, ThermalSpec(True))
        inputs = experiment_library()[3].commands()
        predicted = execute_model(fitted.executable_model(), inputs)
        self.assertTrue(np.isfinite(predicted).all())
        self.assertTrue(np.allclose(predicted, fitted.predict(inputs)))
        self.assertLess(fitted.training_rmse_c, .15)
        self.assertLessEqual(fitted.sensitivity_rank, len(fitted.rates))
        self.assertTrue(fitted.to_dict()["supplied_family"])

    def test_export_cannot_add_executable_code_or_fake_parameter(self):
        model = {"specification": {"type": "two_node_thermal", "sensor_lag": False},
                 "estimated_parameters": {"not_a_parameter": 1.}}
        with self.assertRaises(ValueError):
            execute_model(model, [[0., 0.]])
        with self.assertRaises(ValueError):
            execute_model({**model, "code": "print(1)"}, [[0., 0.]])


if __name__ == "__main__":
    unittest.main()
