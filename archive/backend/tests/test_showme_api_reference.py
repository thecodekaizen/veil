"""Teach API accepts an optional instruction PDF without making a live model call."""

import copy
import io
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from showme.api import app


PROCESS = {
    "task_summary": "Stack the red block on the blue block.",
    "objects": [
        {"id": "red", "label": "red block", "visual_description": "red cube"},
        {"id": "blue", "label": "blue block", "visual_description": "blue cube"},
    ],
    "states": [
        {"id": "separate", "description": "Blocks are apart", "observable_facts": ["visible gap"]},
        {"id": "stacked", "description": "Red block rests on blue", "observable_facts": ["red above blue"]},
    ],
    "transitions": [{
        "id": "stack",
        "from_state": "separate",
        "action": "Place red block on blue block",
        "object_ids": ["red", "blue"],
        "to_state": "stacked",
        "candidate_constraints": [],
        "postconditions": ["red above blue"],
        "evidence": [],
        "reference_evidence": [{"page": 1, "step": "1", "observation": "The diagram shows red placed on blue."}],
    }],
    "ordering_observations": [],
    "uncertainties": [],
}


class LearnReferenceUploadTests(unittest.TestCase):
    def test_optional_pdf_reaches_learning_adapter_and_is_reported(self):
        learner = Mock()
        learner.learn.side_effect = lambda video, **kwargs: {
            **copy.deepcopy(PROCESS),
            "_run": {"model": "muse-spark-1.3", "usage": {"input_tokens": 1, "output_tokens": 1}},
        }
        video_metadata = {
            "duration_seconds": 2.0,
            "width": 640,
            "height": 480,
            "audio_present": False,
        }
        with TestClient(app) as client, \
             patch("showme.api._repo_key_exists", return_value=True), \
             patch("showme.api.MuseSparkClient.from_env", return_value=learner), \
             patch("showme.api.inspect_video", return_value=video_metadata), \
             patch("showme.api.make_model_video", return_value={"filename": "model-input.mp4"}):
            response = client.post(
                "/api/skills/learn",
                files={
                    "video": ("demo.mp4", io.BytesIO(b"video-bytes"), "video/mp4"),
                    "reference_pdf": ("lego-instructions.pdf", io.BytesIO(b"%PDF-1.4 sample"), "application/pdf"),
                },
                data={"narration": "The tab faces outward."},
            )

        self.assertEqual(response.status_code, 200, response.text)
        reference_path = learner.learn.call_args.kwargs["reference_pdf"]
        self.assertEqual(Path(reference_path).name, "reference.pdf")
        self.assertFalse(Path(reference_path).exists(), "temporary reference must be removed after the request")
        self.assertEqual(response.json()["process"]["_run"]["reference_filename"], "lego-instructions.pdf")

    def test_rejects_non_pdf_reference(self):
        with TestClient(app) as client:
            response = client.post(
                "/api/skills/learn",
                files={
                    "video": ("demo.mp4", io.BytesIO(b"video-bytes"), "video/mp4"),
                    "reference_pdf": ("notes.txt", io.BytesIO(b"not a pdf"), "text/plain"),
                },
            )
        self.assertEqual(response.status_code, 415)


if __name__ == "__main__":
    unittest.main()
