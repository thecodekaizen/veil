"""Source-boundary and citation validation for raw Muse discovery."""

from __future__ import annotations
import json
from pathlib import Path
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import httpx2
from openai import APIConnectionError

from thread_engine import raw_discovery
from thread_engine.cli import _render_raw_discovery
from thread_engine.raw_discovery import (
    DiscoveryValidationError,
    load_raw_archive,
    validate_discovery,
)

ROOT = Path(__file__).resolve().parents[2]
DATASET = ROOT / "datasets/synthetic/creative-evolution.json"


class RawArchiveTests(unittest.TestCase):
    def test_loader_projects_only_project_and_raw_artifacts(self) -> None:
        archive = load_raw_archive(DATASET)
        self.assertEqual(set(archive), {"project", "artifacts"})
        self.assertEqual(len(archive["artifacts"]), 6)
        self.assertEqual(
            set(archive["artifacts"][0]),
            {"id", "date", "modality", "title", "content"},
        )

    def test_loader_rejects_invalid_dates_before_model_call(self) -> None:
        data = json.loads(DATASET.read_text(encoding="utf-8"))
        data["artifacts"][0]["date"] = "2025-02-30"
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "invalid.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid date"):
                load_raw_archive(path)


class CitationValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.archive = load_raw_archive(DATASET)

    def candidate(self) -> dict[str, object]:
        return {
            "observations": [
                {"artifact_id": "artifact-001", "date": "2022-03-14", "observation": "Early brief focuses on routes.", "evidence_stage": "planned"},
                {"artifact_id": "artifact-005", "date": "2025-02-08", "observation": "Stories lead the later draft.", "evidence_stage": "released"},
            ],
            "candidate_finding": "The project appears to become more story-led while retaining wayfinding.",
            "supporting_artifacts": [
                {"artifact_id": "artifact-001", "date": "2022-03-14", "relevance": "Early navigation goal."},
                {"artifact_id": "artifact-005", "date": "2025-02-08", "relevance": "Later stories lead."},
            ],
            "complicating_artifacts": [
                {"artifact_id": "artifact-006", "date": "2025-11-21", "relevance": "Route index remains."}
            ],
            "limitations": "Synthetic archive with gaps.",
        }

    def test_valid_timeline_citations_are_accepted_and_marked_unconfirmed(self) -> None:
        result = validate_discovery(self.candidate(), self.archive)
        self.assertTrue(result["human_confirmation_required"])
        self.assertEqual(result["project"]["title"], "Neighborhood Atlas")  # type: ignore[index]

    def test_assertive_candidate_is_withheld(self) -> None:
        value = self.candidate()
        value["candidate_finding"] = "The project focus shifted from navigation to oral history."
        with self.assertRaisesRegex(DiscoveryValidationError, "explicit tentative wording"):
            validate_discovery(value, self.archive)

    def test_fabricated_artifact_is_rejected(self) -> None:
        value = self.candidate()
        value["supporting_artifacts"][1]["artifact_id"] = "artifact-999"  # type: ignore[index]
        with self.assertRaisesRegex(DiscoveryValidationError, "unknown artifact"):
            validate_discovery(value, self.archive)

    def test_mismatched_source_date_is_rejected(self) -> None:
        value = self.candidate()
        value["supporting_artifacts"][0]["date"] = "2020-01-01"  # type: ignore[index]
        with self.assertRaisesRegex(DiscoveryValidationError, "mismatched date"):
            validate_discovery(value, self.archive)

    def test_observation_with_unknown_evidence_stage_is_rejected(self) -> None:
        for stage in ("probably-released", ["released"]):
            with self.subTest(stage=stage):
                value = self.candidate()
                value["observations"][0]["evidence_stage"] = stage  # type: ignore[index]
                with self.assertRaisesRegex(DiscoveryValidationError, "recognized stage"):
                    validate_discovery(value, self.archive)

    def test_observation_still_requires_matching_source_and_date(self) -> None:
        value = self.candidate()
        value["observations"][0]["date"] = "2020-01-01"  # type: ignore[index]
        with self.assertRaisesRegex(DiscoveryValidationError, "observation cites an unknown artifact or mismatched date"):
            validate_discovery(value, self.archive)

    def test_cli_timeline_shows_observation_evidence_stage(self) -> None:
        rendered = _render_raw_discovery({
            "project": {"title": "Example"},
            "model": "muse-spark-1.3",
            "candidate_finding": "The project appears to broaden.",
            "observations": [{
                "date": "2025-02-08",
                "artifact_id": "artifact-005",
                "evidence_stage": "released",
                "observation": "The illustrated story collection is released.",
            }],
        })
        self.assertIn("artifact-005 · released", rendered)

    def test_evolution_needs_multiple_distinct_source_dates(self) -> None:
        value = self.candidate()
        value["supporting_artifacts"] = [value["supporting_artifacts"][0]]  # type: ignore[index]
        with self.assertRaisesRegex(DiscoveryValidationError, "at least two"):
            validate_discovery(value, self.archive)

    def test_evolution_support_must_anchor_earliest_and_latest_timeline_quarters(self) -> None:
        value = self.candidate()
        value["supporting_artifacts"] = [
            {"artifact_id": "artifact-003", "date": "2023-01-19", "relevance": "Middle stage."},
            {"artifact_id": "artifact-006", "date": "2025-11-21", "relevance": "Latest stage."},
        ]
        with self.assertRaisesRegex(DiscoveryValidationError, "No sufficiently supported evolution finding.*earliest and latest timeline quarters"):
            validate_discovery(value, self.archive)

    def test_empty_candidate_is_valid_when_evidence_is_insufficient(self) -> None:
        value = self.candidate()
        value["candidate_finding"] = ""
        value["supporting_artifacts"] = []
        result = validate_discovery(value, self.archive)
        self.assertEqual(result["candidate_finding"], "")


class PaidCallFailureTests(unittest.TestCase):
    def test_connection_failure_is_actionable_and_sdk_retries_are_disabled(self) -> None:
        failure = APIConnectionError(
            message="temporary DNS failure",
            request=httpx2.Request("POST", "https://api.meta.ai/v1/responses"),
        )
        with tempfile.TemporaryDirectory() as folder:
            with (
                patch.object(raw_discovery, "CACHE_DIR", Path(folder)),
                patch.object(raw_discovery, "_load_api_key", return_value="test-key"),
                patch("openai.OpenAI") as openai_client,
            ):
                openai_client.return_value.responses.create.side_effect = failure
                with self.assertRaisesRegex(
                    ValueError,
                    "Could not connect to the Meta Model API.*Automatic retries are disabled.*check Meta Billing",
                ):
                    raw_discovery.discover_raw_archive(DATASET)

                self.assertEqual(openai_client.call_args.kwargs["max_retries"], 0)
                self.assertEqual(openai_client.return_value.responses.create.call_count, 1)

    def test_incomplete_response_reason_is_reported_and_cached_without_retry(self) -> None:
        fake_response = SimpleNamespace(
            output_text='{"observations":',
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
            usage=SimpleNamespace(input_tokens=100, output_tokens=4096),
        )
        with tempfile.TemporaryDirectory() as folder:
            cache_dir = Path(folder)
            with (
                patch.object(raw_discovery, "CACHE_DIR", cache_dir),
                patch.object(raw_discovery, "_load_api_key", return_value="test-key"),
                patch("openai.OpenAI") as openai_client,
            ):
                openai_client.return_value.responses.create.return_value = fake_response
                for _ in range(2):
                    with self.assertRaisesRegex(
                        DiscoveryValidationError,
                        "status=incomplete, reason=max_output_tokens.*cached to avoid a repeat charge",
                    ):
                        raw_discovery.discover_raw_archive(DATASET)

                self.assertEqual(openai_client.return_value.responses.create.call_count, 1)
                cache = json.loads((cache_dir / "raw-discoveries.json").read_text(encoding="utf-8"))
                cached = next(iter(cache.values()))
                self.assertEqual(cached["incomplete_reason"], "max_output_tokens")
                self.assertEqual(cached["status"], "incomplete")

    def test_rejected_paid_output_is_metered_and_cached(self) -> None:
        invalid_finding = {
            "observations": [],
            "candidate_finding": "The project focus shifted from navigation to oral history.",
            "supporting_artifacts": [
                {"artifact_id": "artifact-001", "date": "2022-03-14", "relevance": "Early"},
                {"artifact_id": "artifact-005", "date": "2025-02-08", "relevance": "Later"},
            ],
            "complicating_artifacts": [],
            "limitations": "Synthetic archive.",
        }
        fake_response = SimpleNamespace(
            output_text=json.dumps(invalid_finding),
            usage=SimpleNamespace(input_tokens=100, output_tokens=80),
        )
        with tempfile.TemporaryDirectory() as folder:
            cache_dir = Path(folder)
            with (
                patch.object(raw_discovery, "CACHE_DIR", cache_dir),
                patch.object(raw_discovery, "_load_api_key", return_value="test-key"),
                patch("openai.OpenAI") as openai_client,
            ):
                openai_client.return_value.responses.create.return_value = fake_response
                for _ in range(2):
                    with self.assertRaisesRegex(DiscoveryValidationError, "explicit tentative wording"):
                        raw_discovery.discover_raw_archive(DATASET)

                self.assertEqual(openai_client.return_value.responses.create.call_count, 1)
                self.assertEqual(
                    openai_client.return_value.responses.create.call_args.kwargs["reasoning"],
                    {"effort": "minimal"},
                )
                usage_lines = (cache_dir / "usage.jsonl").read_text(encoding="utf-8").splitlines()
                self.assertEqual(len(usage_lines), 1)
                self.assertTrue((cache_dir / "raw-discoveries.json").exists())


if __name__ == "__main__":
    unittest.main()
