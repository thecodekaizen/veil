import copy
import unittest
from fastapi.testclient import TestClient
from showme.api import app
from showme.guidance import build_guidance
from showme.session import process_fingerprint
from test_showme_process import VALID_PROCESS


class GuidanceTests(unittest.TestCase):
    def setUp(self):
        self.report={'assessment':'possible_difference', 'relations':[{
            'object_ids':['red','blue'], 'relationship':'facing', 'reference_visibility':'visible',
            'learner_visibility':'visible', 'reference_landmark':'Red above blue',
            'learner_landmark':'Red beside blue', 'assessment':'differs', 'explanation':'Different relation'}],
            'uncertainties':[], 'view_guidance':'', '_run':{
                'transition_id':VALID_PROCESS['transitions'][0]['id'],
                'process_sha256':process_fingerprint(VALID_PROCESS)}}

    def guidance(self):
        return build_guidance(VALID_PROCESS,self.report,'joint-inspection')

    def test_difference_links_source_not_invented_repair(self):
        result=self.guidance()
        self.assertEqual(result['decision'],'review_difference')
        self.assertEqual(result['repair_steps'],[])
        self.assertEqual(result['repair_status'],'not_established')
        self.assertEqual(result['evidence']['video'],VALID_PROCESS['transitions'][0]['evidence'])

    def test_unclear_requests_view(self):
        self.report['assessment']='unclear';self.report['relations'][0]['assessment']='unclear'
        self.report['view_guidance']='Expose connector'
        self.assertEqual(self.guidance()['message'],'Expose connector')

    def test_match_does_not_certify_completion(self):
        self.report['assessment']='matches';self.report['relations'][0]['assessment']='matches'
        result=self.guidance()
        self.assertEqual(result['decision'],'continue_observing')
        self.assertEqual(result['repair_steps'],[])

    def test_stale_process_report_rejected(self):
        self.report['_run']['process_sha256']='stale'
        with self.assertRaisesRegex(ValueError,'revision'):self.guidance()

    def test_missing_provenance_rejected(self):
        self.report.pop('_run')
        with self.assertRaisesRegex(ValueError,'provenance'):self.guidance()

    def test_unknown_report_kind_rejected(self):
        with self.assertRaisesRegex(ValueError,'unsupported'):
            build_guidance(VALID_PROCESS,self.report,'simulation')

    def test_does_not_mutate_inputs(self):
        original=copy.deepcopy(self.report);self.guidance();self.assertEqual(self.report,original)

    def test_http_guidance_no_provider(self):
        result=TestClient(app).post('/api/skills/guidance',json={
            'process':VALID_PROCESS,'report':self.report,'report_kind':'joint-inspection'})
        self.assertEqual(result.status_code,200,result.text)
        self.assertEqual(result.json()['guidance']['decision'],'review_difference')

    def test_recovery_message_is_scoped_and_status_rederived(self):
        row={'object_ids':['red','blue'],'relationship':'contact','joint_identity':'same_joint',
             'reference_evidence':'Source contact','before_evidence':'Earlier gap','after_evidence':'Later joined',
             'reference_visibility':'visible','before_visibility':'visible','after_visibility':'visible',
             'before_assessment':'differs','after_assessment':'matches'}
        report={'relations':[row],'uncertainties':[],'view_guidance':'','status':'recovery_reported',
                '_run':self.report['_run']}
        result=build_guidance(VALID_PROCESS,report,'joint-recovery')
        self.assertEqual(result['decision'],'review_reported_recovery')
        self.assertIn('completion is not established',result['message'])
        report['status']='no_prior_difference_reported'
        with self.assertRaisesRegex(ValueError,'conflicts'):
            build_guidance(VALID_PROCESS,report,'joint-recovery')
