"""Exercise the observation HTTP boundary with a controlled provider response."""
import copy
import io
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient
from showme.api import app
from showme.observe import OBSERVATION_PROMPT_VERSION
from test_showme_api_reference import PROCESS
import json


class RecoveryApiTests(unittest.TestCase):
    def response(self, repaired_objects):
        return {
            "events": [
                {"time_seconds": 0.2, "action": "inspect", "state_id": "separate", "assessment": "divergent", "object_ids": ["red"], "evidence": "Red is misplaced."},
                {"time_seconds": 1.5, "action": "stack", "state_id": "stacked", "assessment": "consistent", "object_ids": repaired_objects, "evidence": "Visible later arrangement."},
            ],
            "divergences": [{"time_seconds": 0.2, "process_difference": "Red misplaced", "object_ids": ["red"], "evidence": "Red visible beside blue."}],
            "reference_checks": [{"transition_id": "stack", "status": "not_shown", "time_seconds": None, "evidence": "Action not shown.", "next_guidance": "Show the joint."}],
            "uncertainties": [], "recovery_status": "recovered",
            "_run": {"model": "controlled-provider", "usage": {"input_tokens": 1}},
        }

    def post(self, response, reference=None):
        learner = Mock()
        learner.analyze_video.return_value = copy.deepcopy(response)
        metadata = {"duration_seconds": 2.0, "width": 640, "height": 480, "audio_present": False}
        with TestClient(app) as client, \
             patch("showme.api._repo_key_exists", return_value=True), \
             patch("showme.api.MuseSparkClient.from_env", return_value=learner), \
             patch("showme.api.inspect_video", return_value=metadata), \
             patch("showme.api.make_model_video", return_value={}):
            files = {"video": ("attempt.mp4", io.BytesIO(b"video"), "video/mp4")}
            if reference is not None:
                files["reference_pdf"] = ("instructions.pdf", io.BytesIO(reference), "application/pdf")
            return client.post("/api/skills/observe", files=files, data={"process_json": json.dumps(PROCESS)})

    def test_matching_recovery_reaches_browser_with_prompt_version(self):
        response = self.post(self.response(["red", "blue"]))
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["status"], "recovered")
        self.assertEqual(response.json()["observation"]["_run"]["prompt_version"], OBSERVATION_PROMPT_VERSION)

    def test_optional_reference_provenance_survives_http_boundary(self):
        response = self.post(self.response(["red", "blue"]), b"%PDF-test")
        self.assertEqual(response.status_code, 200, response.text)
        run = response.json()["observation"]["_run"]
        self.assertEqual(run["comparison_source"], "attached_reference")
        self.assertEqual(len(run["reference_document"]["sha256"]), 64)
        self.assertEqual(len(run["process_sha256"]), 64)

    def test_no_reference_preserves_extracted_only_provenance(self):
        response = self.post(self.response(["red", "blue"]))
        self.assertEqual(response.json()["observation"]["_run"]["comparison_source"], "extracted_process_only")

    def test_invalid_pdf_is_rejected(self):
        response = self.post(self.response(["red", "blue"]), b"invalid")
        self.assertEqual(response.status_code, 422)

    def test_unrelated_progress_is_rejected_before_rendering(self):
        response = self.post(self.response(["blue"]))
        self.assertEqual(response.status_code, 422, response.text)
        self.assertIn("each affected object", response.json()["detail"])


if __name__ == "__main__":
    unittest.main()
