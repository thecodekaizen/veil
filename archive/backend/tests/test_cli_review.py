"""CLI wiring for raw Muse discovery into the creator review flow."""

from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO
import sys
import unittest
from unittest.mock import patch

from thread_engine import cli


RAW_RESULT = {
    "candidate_finding": "The project appears to broaden into a shared illustrated collection.",
    "project": {"id": "project-ember", "title": "Ember Table"},
    "provider": "meta",
    "model": "muse-spark-1.3",
    "response": {"status": "completed", "incomplete_reason": None},
    "usage": {"input_tokens": 200, "output_tokens": 300, "estimated_usd": 0.0015},
    "supporting_artifacts": [
        {"artifact_id": "ember-001", "date": "2024-01-12", "relevance": "Personal start."},
        {"artifact_id": "ember-006", "date": "2025-09-27", "relevance": "Shared release."},
    ],
    "complicating_artifacts": [],
    "observations": [],
    "limitations": "Synthetic archive.",
    "human_confirmation_required": True,
}


class RawMuseReviewCliTests(unittest.TestCase):
    def test_memory_extraction_cannot_be_mixed_with_discovery_or_review(self) -> None:
        with patch.object(
            sys,
            "argv",
            ["thread-discover", "archive.json", "--raw-muse", "--extract-memories"],
        ):
            with self.assertRaises(SystemExit) as error:
                cli.main()
        self.assertEqual(error.exception.code, 2)

    def test_raw_muse_and_review_are_wired_together(self) -> None:
        with (
            patch.object(sys, "argv", ["thread-discover", "archive.json", "--raw-muse", "--review"]),
            patch("thread_engine.raw_discovery.discover_raw_archive", return_value=RAW_RESULT),
            patch("thread_engine.review.review_finding") as review,
        ):
            self.assertEqual(cli.main(), 0)

        finding = review.call_args.args[0]
        self.assertEqual(finding["discovery_mode"], "raw")
        self.assertEqual(finding["hypothesis"], RAW_RESULT["candidate_finding"])
        self.assertEqual(
            [item["source_id"] for item in finding["supporting_evidence"]],
            ["ember-001", "ember-006"],
        )

    def test_empty_raw_candidate_skips_interview(self) -> None:
        no_candidate = {**RAW_RESULT, "candidate_finding": "", "supporting_artifacts": []}
        output = StringIO()
        with (
            patch.object(sys, "argv", ["thread-discover", "archive.json", "--raw-muse", "--review"]),
            patch("thread_engine.raw_discovery.discover_raw_archive", return_value=no_candidate),
            patch("thread_engine.review.review_finding") as review,
            redirect_stdout(output),
        ):
            self.assertEqual(cli.main(), 0)

        review.assert_not_called()
        self.assertIn("No evolution established from this archive.", output.getvalue())


if __name__ == "__main__":
    unittest.main()
