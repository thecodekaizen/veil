"""Typed contracts at the boundary between source artifacts and discoveries."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class Memory:
    """A concise, dated interpretation of one source artifact."""

    id: str
    source_id: str
    date: str
    modality: str
    title: str
    summary: str
    themes: tuple[str, ...]

    @classmethod
    def from_dict(cls, value: dict[str, Any]) -> "Memory":
        required = ("id", "source_id", "date", "modality", "title", "summary", "themes")
        missing = [field for field in required if field not in value]
        if missing:
            raise ValueError(f"memory is missing required field(s): {', '.join(missing)}")
        for field in ("id", "source_id", "date", "modality", "title", "summary"):
            if not isinstance(value[field], str) or not value[field].strip():
                raise ValueError(f"memory '{field}' must be a non-empty string")
        if (
            not isinstance(value["themes"], list)
            or not all(isinstance(tag, str) and tag.strip() for tag in value["themes"])
        ):
            raise ValueError("memory 'themes' must be a list of non-empty strings")
        return cls(
            id=str(value["id"]),
            source_id=str(value["source_id"]),
            date=str(value["date"]),
            modality=str(value["modality"]),
            title=str(value["title"]),
            summary=str(value["summary"]),
            themes=tuple(value["themes"]),
        )


@dataclass(frozen=True)
class Evidence:
    memory_id: str
    source_id: str
    date: str
    title: str
    summary: str
    theme: str


@dataclass(frozen=True)
class EvolutionFinding:
    id: str
    project_id: str
    project_title: str
    hypothesis: str
    earlier_theme: str
    later_theme: str
    start_date: str
    end_date: str
    supporting_evidence: tuple[Evidence, ...]
    counter_evidence: tuple[Evidence, ...]
    continuity_evidence: tuple[Evidence, ...]
    uncertainty: tuple[str, ...]
    method: str = "deterministic-theme-prevalence"
    extraction_provider: str = "fixture"
    extraction_model: str | None = None


def to_dict(finding: EvolutionFinding) -> dict[str, Any]:
    """Convert the immutable result contract into JSON-ready primitives."""
    result = asdict(finding)
    result["supporting_evidence"] = [asdict(item) for item in finding.supporting_evidence]
    result["counter_evidence"] = [asdict(item) for item in finding.counter_evidence]
    result["continuity_evidence"] = [asdict(item) for item in finding.continuity_evidence]
    result["uncertainty"] = list(finding.uncertainty)
    return result
