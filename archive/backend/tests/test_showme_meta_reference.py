"""Reference-document video learning requests without a live API call."""

import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from showme.meta import MuseSparkClient, _learning_prompt


class ReferenceLearningTests(unittest.TestCase):
    def test_reference_prompt_separates_expected_procedure_from_observed_attempt(self):
        prompt = _learning_prompt(20, has_reference=True)
        self.assertIn("source for intended steps and constraints", prompt)
        self.assertIn("video only as evidence of what this person actually did", prompt)
        self.assertIn("If the PDF and video differ", prompt)
        self.assertIn("up to 20 states and 18 transitions", prompt)

    def test_video_only_prompt_keeps_reference_evidence_empty(self):
        prompt = _learning_prompt(20)
        self.assertIn("Set reference_evidence to an empty array", prompt)
        self.assertIn("at most 8 states and 7 transitions", prompt)

    def test_uploads_and_attaches_reference_pdf_then_deletes_both_files(self):
        response = SimpleNamespace(
            status="completed",
            incomplete_details=None,
            output_text=json.dumps({"task_summary": "test"}),
            id="response-test",
            usage=SimpleNamespace(input_tokens=12, output_tokens=4),
        )
        create_response = Mock(return_value=response)
        create_file = Mock(side_effect=[SimpleNamespace(id="video-id"), SimpleNamespace(id="pdf-id")])
        delete_file = Mock()
        learner = object.__new__(MuseSparkClient)
        learner.client = SimpleNamespace(
            files=SimpleNamespace(create=create_file, delete=delete_file),
            responses=SimpleNamespace(create=create_response),
        )
        learner.model = "muse-spark-1.3"
        learner._api_error = Exception

        with tempfile.TemporaryDirectory() as folder:
            video = Path(folder) / "demo.mp4"
            reference = Path(folder) / "instructions.pdf"
            video.write_bytes(b"video")
            reference.write_bytes(b"%PDF-test")
            result = learner.learn(video, duration_seconds=20, reference_pdf=reference)

        request = create_response.call_args.kwargs
        parts = request["input"][0]["content"]
        self.assertEqual(parts[1], {"type": "input_file", "file_id": "video-id"})
        self.assertEqual(parts[2], {"type": "input_file", "file_id": "pdf-id"})
        self.assertEqual(result["_run"]["reference_filename"], "instructions.pdf")
        self.assertEqual([call.args[0] for call in delete_file.call_args_list], ["video-id", "pdf-id"])


if __name__ == "__main__":
    unittest.main()
