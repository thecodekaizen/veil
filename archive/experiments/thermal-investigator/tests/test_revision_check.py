import unittest
import numpy as np
from thermal_investigator.revision_check import SEEDS, confirmation_schedule, final_schedules
from thermal_investigator.validation import challenges

class RevisionProtocolTests(unittest.TestCase):
    def test_new_seeds(self):
        previous={11,23,37,101,113,127,139,151,163,179,191,211,227,307,331,353,379,401,431,457,479,503,541,601}
        self.assertFalse(previous.intersection(SEEDS))
        self.assertEqual(len(set(SEEDS)),6)
    def test_new_legal_inputs(self):
        previous=[np.asarray(p.commands()) for p in challenges()]
        plans=final_schedules(); self.assertEqual(len(plans),3)
        for p in plans:
            p.validate()
            self.assertFalse(any(np.array_equal(p.commands(),old) for old in previous))
            self.assertFalse(np.array_equal(p.commands(),confirmation_schedule().commands()))
