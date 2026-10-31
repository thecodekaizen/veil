"""Tests for source-linked Muse memory extraction and failed-response accounting."""

from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from thread_engine.meta_provider import MetaModelProvider


USAGE = SimpleNamespace(input_tokens=120, output_tokens=35, input_tokens_details=None)


class MetaMemoryProviderTests(unittest.TestCase):
    def make_provider(self, cache_dir: Path, content: str):
        fake_response = SimpleNamespace(
            output_text=content,
            usage=USAGE,
        )
        fake_client = SimpleNamespace(
            responses=SimpleNamespace(create=unittest.mock.Mock(return_value=fake_response))
        )
        with patch("openai.OpenAI", return_value=fake_client):
            provider = MetaModelProvider(api_key="test-key", cache_dir=cache_dir)
        return provider, fake_client

    def test_project_extraction_copies_dates_and_keeps_tags_consistent(self) -> None:
        archive = {
            "project": {"id": "project-1", "title": "Letterform Study"},
            "artifacts": [
                {"id": "a", "date": "2024-01-02", "modality": "brief", "title": "Start", "content": "Code font."},
                {"id": "b", "date": "2025-02-03", "modality": "note", "title": "Extend", "content": "Code and print font."},
            ],
        }
        output = {"memories": [
            {"source_id": "a", "summary": "Starts as a code font.", "themes": ["type-design", "code"]},
            {"source_id": "b", "summary": "Extends the type family to print while retaining code.", "themes": ["type-design", "code", "print"]},
        ]}
        with tempfile.TemporaryDirectory() as folder:
            provider, fake_client = self.make_provider(Path(folder), json.dumps(output))
            memories = provider.extract_project(archive)

        self.assertEqual([(item.source_id, item.date) for item in memories], [("a", "2024-01-02"), ("b", "2025-02-03")])
        self.assertEqual(memories[0].themes[0], memories[1].themes[0])
        call = fake_client.responses.create.call_args.kwargs
        self.assertEqual(call["max_output_tokens"], 4096)
        self.assertEqual(call["text"]["format"]["schema"]["properties"]["memories"]["items"]["properties"]["source_id"]["enum"], ["a", "b"])

    def test_invalid_paid_project_output_is_cached_and_metered_once(self) -> None:
        archive = {
            "project": {"id": "project-1", "title": "Letterform Study"},
            "artifacts": [
                {"id": "a", "date": "2024-01-02", "modality": "brief", "title": "Start", "content": "Code font."},
            ],
        }
        with tempfile.TemporaryDirectory() as folder:
            cache_dir = Path(folder)
            provider, fake_client = self.make_provider(cache_dir, "{bad json")
            for _ in range(2):
                with self.assertRaisesRegex(ValueError, "cached to avoid a repeat charge|invalid project memory JSON"):
                    provider.extract_project(archive)

            self.assertEqual(fake_client.responses.create.call_count, 1)
            self.assertEqual(len((cache_dir / "usage.jsonl").read_text().splitlines()), 1)


if __name__ == "__main__":
    unittest.main()
