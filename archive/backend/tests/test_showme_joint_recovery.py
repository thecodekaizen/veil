import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from showme.api import app
from showme.joint_recovery import assess_recovery, compare_recovery, recovery_prompt
from test_showme_process import VALID_PROCESS


class JointRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.tid=VALID_PROCESS['transitions'][0]['id']
        self.row={'object_ids':VALID_PROCESS['transitions'][0]['object_ids'], 'relationship':'contact',
            'reference_evidence':'Source surfaces joined', 'before_evidence':'Contact visibly different',
            'after_evidence':'Same contact visibly matches source', 'reference_visibility':'visible',
            'before_visibility':'visible', 'after_visibility':'visible', 'before_assessment':'differs',
            'after_assessment':'matches', 'joint_identity':'same_joint'}
        self.result={'relations':[self.row], 'uncertainties':[], 'view_guidance':''}

    def assess(self):
        return assess_recovery(self.result, VALID_PROCESS, self.tid)

    def test_specific_difference_then_match_is_reported_recovery(self):
        self.assertEqual(self.assess(),'recovery_reported')

    def test_unchanged_matching_views_do_not_establish_recovery(self):
        self.row['before_assessment']='matches'
        self.assertEqual(self.assess(),'no_prior_difference_reported')

    def test_unfixed_or_new_difference_blocks_recovery(self):
        self.row['after_assessment']='differs'
        self.assertEqual(self.assess(),'current_difference_reported')

    def test_unclear_identity_prevents_cross_wing_recovery(self):
        self.row['joint_identity']='unclear';self.result['view_guidance']='Show same joint'
        self.assertEqual(self.assess(),'unclear')

    def test_one_affected_relation_still_wrong_blocks_recovery(self):
        other=copy.deepcopy(self.row);other['relationship']='facing';other['after_assessment']='differs'
        self.result['relations'].append(other)
        self.assertEqual(self.assess(),'current_difference_reported')

    def test_occluded_contact_cannot_be_called_matching(self):
        self.row['after_visibility']='occluded'
        with self.assertRaisesRegex(ValueError,'hidden'):
            self.assess()

    def test_missing_before_source_or_after_evidence_rejected(self):
        self.row['before_evidence']=''
        with self.assertRaisesRegex(ValueError,'separate'):
            self.assess()

    def test_silhouette_does_not_prove_recovery(self):
        self.row['relationship']='overall_arrangement'
        with self.assertRaisesRegex(ValueError,'contact or facing'):
            self.assess()

    def test_undeclared_object_rejected(self):
        self.row['object_ids']=['unknown']
        with self.assertRaisesRegex(ValueError,'declared'):
            self.assess()

    def test_empty_comparison_requires_view_guidance(self):
        self.result['relations']=[]
        with self.assertRaisesRegex(ValueError,'view guidance'):
            self.assess()

    def test_prompt_does_not_assume_mistake(self):
        self.assertIn('do not assume there was a mistake',recovery_prompt(VALID_PROCESS,self.tid))

    def test_real_call_shape_and_identical_frame_guard(self):
        with tempfile.TemporaryDirectory() as directory:
            paths=[Path(directory)/name for name in ['reference.png','before.jpg','after.jpg']]
            for index,p in enumerate(paths):p.write_bytes(str(index).encode())
            client=Mock();client.analyze_images.return_value=copy.deepcopy(self.result)
            result=compare_recovery(client,*paths,VALID_PROCESS,self.tid,1,2)
            self.assertEqual(result['status'],'recovery_reported')
            self.assertEqual(client.analyze_images.call_args.args[0],paths)
            paths[2].write_bytes(paths[1].read_bytes());client.reset_mock()
            with self.assertRaisesRegex(ValueError,'identical'):
                compare_recovery(client,*paths,VALID_PROCESS,self.tid,1,2)
            client.analyze_images.assert_not_called()

    def test_invalid_chronology_rejected_before_provider(self):
        client=Mock()
        for before,after in [(2,1),(1,1),(True,2),(1,float('nan'))]:
            with self.assertRaises(ValueError):
                compare_recovery(client,Path('x'),Path('y'),Path('z'),VALID_PROCESS,self.tid,before,after)
        client.analyze_images.assert_not_called()

    def test_http_response_and_scoped_status(self):
        client=Mock();client.analyze_images.return_value=copy.deepcopy(self.result)
        files={role:(role+'.jpg',io.BytesIO(role.encode()),'image/jpeg') for role in ['reference_image','before_image','after_image']}
        with patch('showme.api.MuseSparkClient.from_env',return_value=client):
            response=TestClient(app).post('/api/skills/compare-recovery',files=files,data={
                'process_json':json.dumps(VALID_PROCESS),'transition_id':self.tid,'before_seconds':'1','after_seconds':'2'})
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(response.json()['status'],'recovery_reported')
