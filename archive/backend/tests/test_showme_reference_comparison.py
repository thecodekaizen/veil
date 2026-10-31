"""Reference context is explicit, optional, and traceable; no model calls."""
import copy
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock
from showme.observe import observation_prompt, observe_video
from test_showme_process import VALID_PROCESS


class ReferenceComparisonTests(unittest.TestCase):
    def test_no_reference_does_not_claim_manual_access(self):
        prompt = observation_prompt(VALID_PROCESS, 5)
        self.assertIn("No reference PDF or expert images are attached", prompt)
        self.assertIn("not independently verify", prompt)
        self.assertNotIn("The attached PDF supplies", prompt)

    def test_attached_reference_checks_source_model_conflicts(self):
        prompt = observation_prompt(VALID_PROCESS, 5, has_reference=True)
        self.assertIn("The attached PDF supplies", prompt)
        self.assertIn("source-model conflict", prompt)
        self.assertIn("Apparent size", prompt)
        self.assertIn("same evidence timestamp", prompt)

    def test_legacy_call_does_not_upload_reference(self):
        client = Mock()
        client.analyze_video.return_value = {}
        result = observe_video(client, Path("clip.mp4"), VALID_PROCESS, 5)
        self.assertNotIn("reference_pdf", client.analyze_video.call_args.kwargs)
        self.assertEqual(result["_run"]["comparison_source"], "extracted_process_only")
        self.assertIsNone(result["_run"]["reference_document"])

    def test_explicit_pdf_forwarded_with_content_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "reference.pdf"
            pdf.write_bytes(b"%PDF-test")
            client = Mock()
            client.analyze_video.return_value = {}
            result = observe_video(client, Path("clip.mp4"), VALID_PROCESS, 5, reference_pdf=pdf)
            self.assertEqual(client.analyze_video.call_args.kwargs["reference_pdf"], pdf.resolve())
            self.assertEqual(result["_run"]["comparison_source"], "attached_reference")
            self.assertEqual(len(result["_run"]["reference_document"]["sha256"]), 64)

    def test_invalid_reference_rejected_before_provider(self):
        with tempfile.TemporaryDirectory() as directory:
            pdf = Path(directory) / "reference.pdf"
            pdf.write_text("not a PDF")
            client = Mock()
            with self.assertRaisesRegex(ValueError, "readable PDF"):
                observe_video(client, Path("clip.mp4"), VALID_PROCESS, 5, reference_pdf=pdf)
            client.analyze_video.assert_not_called()

    def test_process_fingerprint_tracks_claims_but_not_private_metadata(self):
        client = Mock()
        client.analyze_video.side_effect = lambda *args, **kwargs: {}
        first = observe_video(client, Path("clip.mp4"), VALID_PROCESS, 5)
        changed = copy.deepcopy(VALID_PROCESS)
        changed["_run"] = {"private_path": "/local-only"}
        second = observe_video(client, Path("clip.mp4"), changed, 5)
        self.assertEqual(first["_run"]["process_sha256"], second["_run"]["process_sha256"])
        changed["task_summary"] = "A different semantic claim"
        third = observe_video(client, Path("clip.mp4"), changed, 5)
        self.assertNotEqual(first["_run"]["process_sha256"], third["_run"]["process_sha256"])
