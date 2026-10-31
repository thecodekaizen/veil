import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from showme.cli import _inspect_joint
from test_showme_process import VALID_PROCESS


class JointCliTests(unittest.TestCase):
    def test_rejected_output_is_preserved_and_not_retried(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); process=root/'process.json'; process.write_text(json.dumps(VALID_PROCESS))
            reference=root/'source.png'; reference.write_bytes(b'png')
            learner=root/'learner.jpg'; learner.write_bytes(b'jpeg')
            output=root/'run'; client=Mock(); client.analyze_images.return_value={'assessment':'matches','relations':[]}
            with patch('showme.cli.MuseSparkClient.from_env',return_value=client):
                code=_inspect_joint(process,reference,learner,VALID_PROCESS['transitions'][0]['id'],output)
            self.assertEqual(code,2)
            client.analyze_images.assert_called_once()
            self.assertTrue((output/'inspection-unvalidated.json').exists())
            self.assertTrue((output/'failure.json').exists())
            self.assertFalse((output/'inspection.json').exists())

    def test_existing_run_not_overwritten_or_sent(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); process=root/'process.json'; process.write_text(json.dumps(VALID_PROCESS))
            image=root/'source.png'; image.write_bytes(b'png'); output=root/'run'; output.mkdir()
            keep=output/'keep'; keep.write_text('original')
            with patch('showme.cli.MuseSparkClient.from_env') as factory:
                self.assertEqual(_inspect_joint(process,image,image,VALID_PROCESS['transitions'][0]['id'],output),2)
            factory.assert_not_called()
            self.assertEqual(keep.read_text(),'original')
