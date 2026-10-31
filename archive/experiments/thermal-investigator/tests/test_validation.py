import unittest
import numpy as np
from thermal_investigator.validation import challenges, hidden_trace
from thermal_investigator.lab import parameters, trajectory

class ValidationTests(unittest.TestCase):
    def test_challenges_are_bounded_and_distinct(self):
        plans=challenges()
        self.assertEqual(len({p.id for p in plans}),3)
        for plan in plans:
            plan.validate()
            self.assertEqual(np.asarray(plan.commands()).shape,(60,2))
    def test_linear_evaluator_matches_existing_environment(self):
        for delayed in (False,True):
            p=parameters(101,delayed)
            commands=challenges()[0].commands()
            np.testing.assert_allclose(hidden_trace(commands,p),trajectory(np.asarray(commands),p),atol=1e-10)
    def test_nonlinear_loss_reduces_temperature(self):
        p=parameters(101,False); commands=challenges()[1].commands()
        linear=hidden_trace(commands,p); stress=hidden_trace(commands,p,True)
        self.assertTrue(np.all(stress<=linear+1e-10))
        self.assertGreater(float(np.max(linear-stress)),.1)
