import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from thermal_investigator.comparison_audit import audit
from thermal_investigator.physical import ThermalSpec,execute_model

class ComparisonAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        (self.root/'results.json').write_text('{"rows":[]}')
        self.case=self.root/'case-0-0-fixed_bic';self.case.mkdir()
        model={'specification':ThermalSpec(False).to_dict(),'estimated_parameters':dict(zip(ThermalSpec(False).parameter_names(),[.01,.01,.008,.008,.3,.25]))}
        u=[[.3,.3]]*60;y=execute_model(model,u).tolist()
        self.write('prediction-commit.json',{'model':model,'inputs':{'commands_fraction':u},'prediction':y})
        digest=hashlib.sha256((self.case/'prediction-commit.json').read_bytes()).hexdigest()
        self.write('result.json',{'status':'completed','prediction_sha256':digest,'mean_rmse_c':0.,'experiment_actions_used':3,'fits_used':3})
        self.write('challenge-score.json',{'temperature_c':y,'mean_rmse_c':0.})
        obs={'commands_fraction':u,'temperature_c':y,'ambient_c':22.,'sample_interval_s':2.}
        self.write('investigation-export.json',{'session':{'used':3},'observations':[{'id':f'initial-{i}','body':json.dumps(obs)} for i in range(3)]})
    def tearDown(self):self.tmp.cleanup()
    def write(self,name,value):(self.case/name).write_text(json.dumps(value))
    def test_recompute_and_mark_incomplete_batch(self):
        result=audit(self.root)
        self.assertEqual(result['status'],'consistent');self.assertFalse(result['complete'])
        self.assertEqual(result['completed_case_records'],1)
    def test_score_tampering_rejected(self):
        result=json.loads((self.case/'result.json').read_text());result['mean_rmse_c']=1.
        self.write('result.json',result)
        with self.assertRaises(ValueError):audit(self.root)
