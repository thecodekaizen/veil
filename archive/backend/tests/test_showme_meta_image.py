"""Unit tests for single-frame Muse image requests without a live API call."""

import base64
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock

from showme.meta import MuseSparkClient


class MuseImageRequestTests(unittest.TestCase):
    def test_sends_image_as_inline_data_url_with_structured_output(self):
        response = SimpleNamespace(
            status="completed",
            incomplete_details=None,
            output_text=json.dumps({"assessment": "unclear"}),
            id="response-test",
            usage=SimpleNamespace(input_tokens=12, output_tokens=4),
        )
        create = Mock(return_value=response)
        learner = object.__new__(MuseSparkClient)
        learner.client = SimpleNamespace(responses=SimpleNamespace(create=create))
        learner.model = "muse-spark-1.3"

        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder) / "frame.jpg"
            image.write_bytes(b"jpeg-bytes")
            output = learner.analyze_image(
                image,
                prompt="Inspect one frame.",
                schema={"type": "object"},
                schema_name="snapshot_test",
            )

        request = create.call_args.kwargs
        image_part = request["input"][0]["content"][1]
        self.assertEqual(image_part["type"], "input_image")
        self.assertEqual(image_part["image_url"], f"data:image/jpeg;base64,{base64.b64encode(b'jpeg-bytes').decode('ascii')}")
        self.assertEqual(request["text"]["format"]["name"], "snapshot_test")
        self.assertEqual(output["_run"]["usage"], {"input_tokens": 12, "output_tokens": 4})
        self.assertIsNone(output["_run"]["remote_file_id"])

    def test_multi_image_adapter_preserves_roles_and_mime_types(self):
        learner = object.__new__(MuseSparkClient)
        learner._structured_response = Mock(return_value={"assessment": "unclear"})
        with tempfile.TemporaryDirectory() as folder:
            reference = Path(folder) / "reference.png"
            current = Path(folder) / "current.jpg"
            reference.write_bytes(b"png"); current.write_bytes(b"jpg")
            learner.analyze_images([reference, current], prompt="Compare", schema={}, schema_name="joint")
        content = learner._structured_response.call_args.args[0]
        self.assertEqual(content[1]["text"], "Evidence image 0")
        self.assertTrue(content[2]["image_url"].startswith("data:image/png;base64,"))
        self.assertEqual(content[3]["text"], "Evidence image 1")
        self.assertTrue(content[4]["image_url"].startswith("data:image/jpeg;base64,"))

    def test_multi_image_count_rejected_before_request(self):
        learner = object.__new__(MuseSparkClient)
        with self.assertRaises(ValueError):
            learner.analyze_images([], prompt="Compare", schema={}, schema_name="joint")


if __name__ == "__main__":
    unittest.main()
