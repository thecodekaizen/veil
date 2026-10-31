"""Application service shared by the CLI and the HTTP API."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from .cli import load_dataset
from .contracts import to_dict
from .discovery import discover_evolution

ProviderName = Literal["fixture", "meta"]
DEFAULT_DATASET = Path(__file__).resolve().parents[2] / "datasets" / "synthetic" / "creative-evolution.json"


def extract_dataset_memories(*, dataset_path: Path = DEFAULT_DATASET) -> dict[str, Any]:
    """Extract source-linked temporal memories from a raw archive using Meta."""
    from .raw_discovery import load_raw_archive
    from .meta_provider import MetaModelProvider

    archive = load_raw_archive(dataset_path)
    provider = MetaModelProvider.from_env()
    memories = provider.extract_project(archive)
    return {
        "project": archive["project"],
        "provider": "meta",
        "model": provider.model,
        "memories": [
            {
                "id": item.id,
                "source_id": item.source_id,
                "date": item.date,
                "modality": item.modality,
                "title": item.title,
                "summary": item.summary,
                "themes": list(item.themes),
            }
            for item in memories
        ],
        "api_usage": provider.usage_summary(),
    }


def discover_dataset(
    *, dataset_path: Path = DEFAULT_DATASET, provider_name: ProviderName = "fixture"
) -> dict[str, Any]:
    """Run extraction and temporal analysis, returning one JSON-ready finding."""
    model = None
    usage = None
    if provider_name == "meta":
        from .raw_discovery import load_raw_archive

        archive = load_raw_archive(dataset_path)
        project_id = archive["project"]["id"]
        project_title = archive["project"]["title"]
        from .meta_provider import MetaModelProvider

        provider = MetaModelProvider.from_env()
        memories = provider.extract_project(archive)
        model = provider.model
        usage = provider.usage_summary()
    else:
        project_id, project_title, memories = load_dataset(dataset_path)

    finding = discover_evolution(
        project_id=project_id,
        project_title=project_title,
        memories=memories,
        extraction_provider=provider_name,
        extraction_model=model,
    )
    if finding is None:
        raise ValueError("No sufficiently supported evolution finding in this dataset.")
    result = to_dict(finding)
    if usage is not None:
        result["api_usage"] = usage
    return result
