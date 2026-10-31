import unittest
import numpy as np
from thermal_investigator.adequacy import assess, choose_probe, probe_library

class AdequacyTests(unittest.TestCase):
    def test_pass_is_scoped_to_probe(self):
        a=assess([[22,22],[23,23]],[[22,22],[23,23]])
        self.assertEqual(a['status'],'no_mismatch_observed')
        self.assertIn('does not certify',a['scope'])
    def test_mismatch_detected(self):
        self.assertEqual(assess([[22,22],[23,23]],[[22,22],[24,24]])['status'],'model_mismatch_observed')
    def test_reject_bad_measurements(self):
        for value in ([[22,22]],[[22,22],[np.nan,23]]):
            with self.assertRaises(ValueError): assess([[22,22],[23,23]],value)
    def test_probe_bounds(self):
        for p in probe_library(): p.validate()
        self.assertEqual(choose_probe([], 'fixed-sustained').id,'sustained-both')
        with self.assertRaises(ValueError): choose_probe([], 'unknown')
        with self.assertRaises(ValueError): choose_probe([], 'model-disagreement')
