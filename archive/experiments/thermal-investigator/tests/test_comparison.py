import unittest
from thermal_investigator.comparison import protocol,SEEDS,select

class PairedProtocolTests(unittest.TestCase):
    def test_paid_cap_and_unrestricted_start(self):
        p=protocol()
        self.assertEqual(len(SEEDS)*2*2*p['max_calls_per_Meta_case'],p['max_Meta_calls_total'])
        self.assertEqual(len(SEEDS)*2*2*p['guard_per_Meta_case_usd'],p['aggregate_local_guard_usd'])
        self.assertEqual(p['maximum_fits'],9)
        self.assertIn('all three',p['initial_selection'])
        self.assertTrue(p['no_automatic_retries'])
    def test_fresh_instance_seeds(self):
        self.assertEqual(len(set(SEEDS)),5)
        self.assertTrue(all(s>1019 for s in SEEDS))
