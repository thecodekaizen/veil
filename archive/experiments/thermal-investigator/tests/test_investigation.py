import tempfile
import unittest
from pathlib import Path
from thermal_investigator.investigation import Investigation
from thermal_investigator.physical import ThermalSpec, execute_model
from thermal_investigator.contracts import initial_schedule

MODEL={'specification':ThermalSpec(False).to_dict(),'estimated_parameters':dict(zip(ThermalSpec(False).parameter_names(),[.01,.01,.008,.008,.3,.25]))}
def observation(plan,offset=0):
    return {'commands_fraction':plan.commands(),'temperature_c':(execute_model(MODEL,plan.commands())+offset).tolist(),'ambient_c':22.,'sample_interval_s':2.}

class InvestigationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.path=Path(self.tmp.name)/'session.db'
        self.i=Investigation(self.path); self.plan=initial_schedule()
        self.i.create('s',3,[observation(self.plan)])
        self.i.add_model('s','v1',MODEL,['initial-0'])
    def tearDown(self): self.i.close(); self.tmp.cleanup()
    def prepare(self): return self.i.prepare('s','probe','v1',self.plan.to_dict())
    def test_resume_does_not_recharge_or_repeat(self):
        self.prepare(); self.i.close(); self.i=Investigation(self.path); self.prepare()
        calls=[]
        def runner(action,plan): calls.append(action); return observation(self.plan)
        first=self.i.execute('s','probe',runner)
        self.assertEqual(self.i.execute('s','probe',runner),first)
        self.assertEqual(calls,['probe']); self.assertEqual(self.i.export('s')['session']['used'],2)
    def test_uncertain_dispatch_never_retries(self):
        self.prepare()
        def fail(*args): raise TimeoutError('unknown remote outcome')
        with self.assertRaises(TimeoutError): self.i.execute('s','probe',fail)
        self.i.close(); self.i=Investigation(self.path)
        with self.assertRaises(RuntimeError): self.i.execute('s','probe',lambda *a:self.fail('must not execute'))
        result=self.i.reconcile('s','probe',observation(self.plan))
        self.assertEqual(result['verdict'],'no_mismatch_observed')
    def test_revision_requires_mismatch_then_confirmation(self):
        self.prepare()
        self.i.execute('s','probe',lambda *a:observation(self.plan,1.))
        self.i.add_model('s','v2',MODEL,['initial-0','probe'],parent='v1')
        self.i.prepare('s','confirm','v2',self.plan.to_dict(),'confirmation')
        result=self.i.execute('s','confirm',lambda *a:observation(self.plan))
        self.assertEqual(result['verdict'],'revision_supported_on_confirmation')
        with self.assertRaises(ValueError): self.i.prepare('s','extra','v2',self.plan.to_dict())
        self.assertEqual(len(self.i.export('s')['models']),2)
    def test_failed_confirmation_stays_visible(self):
        self.prepare(); self.i.execute('s','probe',lambda *a:observation(self.plan,1.))
        self.i.add_model('s','v2',MODEL,['probe'],parent='v1')
        self.i.prepare('s','confirm','v2',self.plan.to_dict(),'confirmation')
        self.assertEqual(self.i.execute('s','confirm',lambda *a:observation(self.plan,1.))['verdict'],'revision_rejected')
    def test_cannot_revise_from_success_or_unknown_evidence(self):
        self.prepare(); self.i.execute('s','probe',lambda *a:observation(self.plan))
        with self.assertRaises(ValueError): self.i.add_model('s','v2',MODEL,['probe'],parent='v1')
        with self.assertRaises(ValueError): self.i.add_model('s','v2',MODEL,['missing'],parent='v1')
    def test_reused_id_cannot_change_request(self):
        self.prepare()
        with self.assertRaises(ValueError): self.i.prepare('s','probe','v1',self.plan.to_dict(),'confirmation')
    def test_bad_measurement_preserves_uncertain_state(self):
        self.prepare()
        with self.assertRaises(ValueError): self.i.execute('s','probe',lambda *a:{**observation(self.plan),'temperature_c':[[22,22]]})
        self.assertEqual(self.i.export('s')['actions'][0]['status'],'dispatched')
    def test_confirmation_requires_revision(self):
        with self.assertRaises(ValueError): self.i.prepare('s','c','v1',self.plan.to_dict(),'confirmation')
