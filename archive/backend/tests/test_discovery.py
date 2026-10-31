"""Temporal comparison must show themes that continue across periods."""

from __future__ import annotations

import unittest

from thread_engine.contracts import Memory, to_dict
from thread_engine.discovery import discover_evolution


class ContinuityEvidenceTests(unittest.TestCase):
    def test_persistent_topic_is_returned_separately_from_shift_evidence(self) -> None:
        memories = [
            Memory("m1", "s1", "2023-01-01", "brief", "Start", "A code tool.", ("developer tools", "code readability")),
            Memory("m2", "s2", "2023-04-01", "test", "Test", "Tests code.", ("developer tools", "code readability")),
            Memory("m3", "s3", "2023-08-01", "note", "Note", "Still code-focused.", ("developer tools", "code readability")),
            Memory("m4", "s4", "2024-01-01", "trial", "Trial", "Adds readable print text.", ("text readability", "code readability")),
            Memory("m5", "s5", "2024-05-01", "prototype", "Prototype", "Adds labels and text.", ("text readability", "code readability")),
            Memory("m6", "s6", "2024-09-01", "release", "Release", "Keeps coding and adds text.", ("text readability", "code readability")),
        ]

        finding = discover_evolution(
            project_id="p1", project_title="Type Study", memories=memories, extraction_provider="meta"
        )

        self.assertIsNotNone(finding)
        result = to_dict(finding)
        self.assertEqual(result["earlier_theme"], "developer tools")
        self.assertEqual(result["later_theme"], "text readability")
        self.assertEqual(
            {item["theme"] for item in result["continuity_evidence"]},
            {"code readability"},
        )
        self.assertEqual(
            {item["source_id"] for item in result["continuity_evidence"]},
            {"s4", "s5", "s6"},
        )


if __name__ == "__main__":
    unittest.main()
