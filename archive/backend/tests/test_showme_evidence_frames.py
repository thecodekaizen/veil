"""Local evidence extraction must not upload, overwrite, or invent labels."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from showme.media import extract_evidence_frames


class EvidenceFrameTests(unittest.TestCase):
    def test_invalid_times_rejected_before_inspection(self):
        for times in ([], [True], [-1], [float("nan")], [float("inf")], list(range(61))):
            with self.subTest(times=times), patch("showme.media.inspect_video") as inspect:
                with self.assertRaises(ValueError):
                    extract_evidence_frames(Path("v.mov"), Path("unused"), times)
                inspect.assert_not_called()

    def test_packet_preserves_times_hashes_and_no_labels(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "frames"
            def render(args):
                Path(args[-1]).write_bytes(b"image")
            with patch("showme.media.inspect_video", return_value={"duration_seconds": 5, "source_sha256": "source"}), patch("showme.media._run", side_effect=render):
                result = extract_evidence_frames(Path("v.mov"), output, [3, 1, 3])
            self.assertEqual([f["requested_time_seconds"] for f in result["frames"]], [1, 3])
            self.assertEqual(len(result["frames"][0]["sha256"]), 64)
            self.assertNotIn("assessment", json.dumps(result))
            self.assertEqual(json.loads((output / "manifest.json").read_text()), result)

    def test_outside_clip_does_not_create_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "frames"
            with patch("showme.media.inspect_video", return_value={"duration_seconds": 5}):
                with self.assertRaises(ValueError):
                    extract_evidence_frames(Path("v.mov"), output, [5])
            self.assertFalse(output.exists())

    def test_existing_output_untouched(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            (output / "keep").write_text("original")
            with patch("showme.media.inspect_video", return_value={"duration_seconds": 5}):
                with self.assertRaises(FileExistsError):
                    extract_evidence_frames(Path("v.mov"), output, [1])
            self.assertEqual((output / "keep").read_text(), "original")

    def test_render_failure_removes_partial_packet(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "frames"
            with patch("showme.media.inspect_video", return_value={"duration_seconds": 5}), patch("showme.media._run", side_effect=RuntimeError("decode failed")):
                with self.assertRaises(RuntimeError):
                    extract_evidence_frames(Path("v.mov"), output, [1])
            self.assertFalse(output.exists())
