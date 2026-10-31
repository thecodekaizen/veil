"""Service-level tests for raw-source Meta extraction and provenance."""

from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from thread_engine.contracts import Memory
from thread_engine.service import discover_dataset, extract_dataset_memories

ROOT = Path(__file__).resolve().parents[2]
RAW_DATASET = ROOT / "datasets/synthetic/experiments/type-foundry/raw.json"


class FakeMemoryProvider:
    model = "test-model"
    received_artifact_keys: list[set[str]] = []

    def extract(self, artifact: dict[str, str]) -> Memory:
        self.received_artifact_keys.append(set(artifact))
        if artifact["id"] in {"type-001", "type-002", "type-003"}:
            themes = ("code", "monospace") if artifact["id"] == "type-001" else ("code",)
        else:
            themes = ("editorial-readability", "code") if artifact["id"] == "type-006" else ("editorial-readability",)
        return Memory(
            id=f"memory-{artifact['id']}",
            source_id=artifact["id"],
            date=artifact["date"],
            modality=artifact["modality"],
            title=artifact["title"],
            summary=f"Extracted from {artifact['title']}.",
            themes=themes,
        )

    def usage_summary(self) -> dict[str, int | float]:
        return {"requests": 1, "cache_hits": 0, "input_tokens": 600, "output_tokens": 120}

    def extract_project(self, archive: dict[str, object]) -> list[Memory]:
        return [self.extract(item) for item in archive["artifacts"]]  # type: ignore[index]


class RawMetaServiceTests(unittest.TestCase):
    def test_extract_memories_returns_dated_source_linked_records(self) -> None:
        fake_provider = FakeMemoryProvider()
        fake_provider.received_artifact_keys = []
        with patch("thread_engine.meta_provider.MetaModelProvider.from_env", return_value=fake_provider):
            result = extract_dataset_memories(dataset_path=RAW_DATASET)

        self.assertEqual(result["provider"], "meta")
        self.assertEqual(len(result["memories"]), 6)
        self.assertEqual(result["memories"][3]["source_id"], "type-004")
        self.assertEqual(result["memories"][3]["date"], "2024-05-14")
        self.assertEqual(set(fake_provider.received_artifact_keys[0]), {"id", "date", "modality", "title", "content"})
        self.assertIn("api_usage", result)

    def test_meta_provider_accepts_raw_only_dataset_and_preserves_provenance(self) -> None:
        fake_provider = FakeMemoryProvider()
        fake_provider.received_artifact_keys = []
        with patch("thread_engine.meta_provider.MetaModelProvider.from_env", return_value=fake_provider):
            result = discover_dataset(dataset_path=RAW_DATASET, provider_name="meta")

        self.assertEqual(result["project_id"], "project-tiny-type-lab")
        self.assertEqual(result["extraction_provider"], "meta")
        self.assertEqual(result["extraction_model"], "test-model")
        self.assertEqual(len(fake_provider.received_artifact_keys), 6)
        self.assertTrue(all(keys == {"id", "date", "modality", "title", "content"} for keys in fake_provider.received_artifact_keys))
        evidence_source_ids = {
            item["source_id"]
            for group in (result["supporting_evidence"], result["counter_evidence"])
            for item in group
        }
        self.assertLessEqual(evidence_source_ids, {f"type-00{index}" for index in range(1, 7)})
        self.assertIn("api_usage", result)


if __name__ == "__main__":
    unittest.main()
