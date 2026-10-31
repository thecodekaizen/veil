import copy
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from fastapi.testclient import TestClient
from showme.api import app
from showme.focus import inspection_prompt, inspect_joint, validate_inspection
from test_showme_process import VALID_PROCESS


class JointInspectionTests(unittest.TestCase):
    def setUp(self):
        self.transition = VALID_PROCESS['transitions'][0]
        self.tid = self.transition['id']
        self.result = {'assessment': 'matches', 'relations': [{
            'object_ids': self.transition['object_ids'], 'reference_landmark': 'Visible source joint',
            'learner_landmark': 'Visible learner joint', 'assessment': 'matches',
            'relationship': 'contact', 'reference_visibility': 'visible', 'learner_visibility': 'visible',
            'explanation': 'Comparable attachment surfaces are visible.'}],
            'uncertainties': [], 'view_guidance': ''}

    def test_valid_selected_joint(self):
        validate_inspection(self.result, VALID_PROCESS, self.tid)

    def test_match_cannot_hide_unclear_relation(self):
        self.result['relations'][0]['assessment'] = 'unclear'
        with self.assertRaisesRegex(ValueError, 'all compared'):
            validate_inspection(self.result, VALID_PROCESS, self.tid)

    def test_difference_needs_conflict(self):
        self.result['assessment'] = 'possible_difference'
        with self.assertRaisesRegex(ValueError, 'conflicting'):
            validate_inspection(self.result, VALID_PROCESS, self.tid)

    def test_unknown_object_rejected(self):
        self.result['relations'][0]['object_ids'] = ['invented']
        with self.assertRaisesRegex(ValueError, 'declared affected'):
            validate_inspection(self.result, VALID_PROCESS, self.tid)

    def test_empty_evidence_rejected(self):
        self.result['relations'][0]['reference_landmark'] = ''
        with self.assertRaisesRegex(ValueError, 'separate source'):
            validate_inspection(self.result, VALID_PROCESS, self.tid)

    def test_unclear_requires_actionable_view_request(self):
        self.result['assessment'] = 'unclear'
        with self.assertRaisesRegex(ValueError, 'view guidance'):
            validate_inspection(self.result, VALID_PROCESS, self.tid)

    def test_prompt_is_scoped_and_does_not_encode_error(self):
        prompt = inspection_prompt(VALID_PROCESS, self.tid)
        self.assertIn('Do not assume this attempt contains an error', prompt)
        self.assertIn('Do not infer action order, recovery', prompt)
        with self.assertRaises(ValueError):
            inspection_prompt(VALID_PROCESS, 'invented')

    def test_client_receives_ordered_images_and_preserves_provenance(self):
        with tempfile.TemporaryDirectory() as d:
            reference, learner = Path(d)/'reference.png', Path(d)/'learner.jpg'
            reference.write_bytes(b'source'); learner.write_bytes(b'learner')
            client = Mock(); client.analyze_images.return_value = copy.deepcopy(self.result)
            result = inspect_joint(client, reference, learner, VALID_PROCESS, self.tid)
            self.assertEqual(client.analyze_images.call_args.args[0], [reference, learner])
            self.assertEqual(result['_run']['transition_id'], self.tid)
            self.assertEqual(len(result['_run']['evidence_images'][0]['sha256']), 64)

    def test_endpoint_forwards_explicit_images_and_returns_inspection(self):
        provider = Mock(); provider.analyze_images.return_value = copy.deepcopy(self.result)
        with patch('showme.api.MuseSparkClient.from_env', return_value=provider):
            result = TestClient(app).post('/api/skills/inspect-joint', data={
                'process_json': json.dumps(VALID_PROCESS), 'transition_id': self.tid}, files={
                'reference_image': ('source.png', io.BytesIO(b'png'), 'image/png'),
                'learner_image': ('frame.jpg', io.BytesIO(b'jpeg'), 'image/jpeg')})
        self.assertEqual(result.status_code, 200, result.text)
        self.assertEqual(result.json()['status'], 'matches')
        self.assertIn('selected joint only', result.json()['inspection']['_run']['scope'])

    def test_endpoint_unknown_transition_never_calls_provider(self):
        with patch('showme.api.MuseSparkClient.from_env') as factory:
            result = TestClient(app).post('/api/skills/inspect-joint', data={
                'process_json': json.dumps(VALID_PROCESS), 'transition_id': 'unknown'}, files={
                'reference_image': ('source.png', io.BytesIO(b'png'), 'image/png'),
                'learner_image': ('frame.jpg', io.BytesIO(b'jpeg'), 'image/jpeg')})
        self.assertEqual(result.status_code, 422)
        factory.assert_not_called()

    def test_silhouette_alone_cannot_establish_joint_match(self):
        self.result['relations'][0]['relationship'] = 'overall_arrangement'
        with self.assertRaisesRegex(ValueError, 'contact or facing'):
            validate_inspection(self.result, VALID_PROCESS, self.tid)

    def test_occluded_contact_cannot_establish_match(self):
        self.result['relations'][0]['learner_visibility'] = 'occluded'
        with self.assertRaisesRegex(ValueError, 'occluded or ambiguous'):
            validate_inspection(self.result, VALID_PROCESS, self.tid)

    def test_ambiguous_source_cannot_establish_difference(self):
        self.result['assessment'] = 'possible_difference'
        self.result['relations'][0]['assessment'] = 'differs'
        self.result['relations'][0]['reference_visibility'] = 'ambiguous'
        with self.assertRaisesRegex(ValueError, 'occluded or ambiguous'):
            validate_inspection(self.result, VALID_PROCESS, self.tid)

    def test_targeted_facing_does_not_request_hidden_contact(self):
        prompt = inspection_prompt(VALID_PROCESS, self.tid, relationship_target='facing')
        self.assertIn('Inspect only the facing relationship', prompt)
        self.assertIn('not a statement of its correct or incorrect value', prompt)
        self.result['relations'][0]['relationship'] = 'facing'
        validate_inspection(self.result, VALID_PROCESS, self.tid, relationship_target='facing')

    def test_unrequested_relationship_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'unrequested'):
            validate_inspection(self.result, VALID_PROCESS, self.tid, relationship_target='facing')

    def test_invalid_target_rejected_before_prompt(self):
        with self.assertRaises(ValueError):
            inspection_prompt(VALID_PROCESS, self.tid, relationship_target='wrong-wing')
