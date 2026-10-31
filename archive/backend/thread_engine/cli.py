"""Command-line entry point for the deterministic discovery baseline."""

from __future__ import annotations

import argparse
from collections import Counter
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from .contracts import Memory


class DatasetError(ValueError):
    """A validation problem in the supplied archive, with a stable error code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def load_dataset(path: Path) -> tuple[str, str, list[Memory]]:
    try:
        data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DatasetError("unreadable", f"cannot read dataset {path}: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise DatasetError("invalid_json", f"invalid JSON in {path}: {exc}") from exc

    if data.get("schema_version") != 1:
        raise DatasetError("schema", "dataset must declare schema_version: 1")
    project = data.get("project")
    if not isinstance(project, dict) or not project.get("id") or not project.get("title"):
        raise DatasetError("project", "dataset must include project.id and project.title")
    raw_memories = data.get("memories")
    if not isinstance(raw_memories, list):
        raise DatasetError("memories", "dataset 'memories' must be a list")
    if not all(isinstance(item, dict) for item in raw_memories):
        raise DatasetError("memory_shape", "each memory must be a JSON object")

    project_ids = {str(item.get("project_id", project["id"])) for item in raw_memories}
    if project_ids and project_ids != {str(project["id"])}:
        raise DatasetError("mixed_projects", "dataset mixes project IDs; split the archive or select one project before discovery")

    try:
        memories = [Memory.from_dict(item) for item in raw_memories]
    except (TypeError, ValueError) as exc:
        raise DatasetError("memory_fields", str(exc)) from exc

    for memory in memories:
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", memory.date):
            raise DatasetError("invalid_date", f"memory {memory.id!r} has invalid date {memory.date!r}; expected YYYY-MM-DD")
        try:
            date.fromisoformat(memory.date)
        except ValueError as exc:
            raise DatasetError("invalid_date", f"memory {memory.id!r} has invalid date {memory.date!r}; expected a real calendar date") from exc

    source_ids = [memory.source_id for memory in memories]
    duplicates = sorted(source_id for source_id, count in Counter(source_ids).items() if count > 1)
    if duplicates:
        raise DatasetError("duplicate_source", f"source_id(s) appear more than once: {', '.join(duplicates)}")
    return str(project["id"]), str(project["title"]), memories


def _render_text(result: dict[str, Any]) -> str:
    lines = [
        f"{result['project_title']} · {result['start_date']} → {result['end_date']}",
        f"Theme extraction: {result['extraction_provider']}"
        + (f" ({result['extraction_model']})" if result.get("extraction_model") else ""),
        "",
        result["hypothesis"],
        "",
        "Supporting evidence:",
    ]
    for item in result["supporting_evidence"]:
        lines.append(f"  + {item['date']} · {item['title']} [{item['source_id']}] — {item['summary']}")
    lines.append("\nCounter-evidence:")
    if result["counter_evidence"]:
        for item in result["counter_evidence"]:
            lines.append(f"  ! {item['date']} · {item['title']} [{item['source_id']}] — {item['summary']}")
    else:
        lines.append("  None found in this fixture.")
    lines.append("\nContinuity evidence:")
    if result.get("continuity_evidence"):
        for item in result["continuity_evidence"]:
            lines.append(f"  = {item['date']} · {item['title']} [{item['source_id']}] — {item['theme']}: {item['summary']}")
    else:
        lines.append("  No shared topic tags found across both periods.")
    lines.append("\nUncertainty:")
    lines.extend(f"  ? {item}" for item in result["uncertainty"])
    return "\n".join(lines)


def _render_raw_discovery(result: dict[str, Any]) -> str:
    project = result.get("project", {})
    lines = [f"{project.get('title', 'Project')} · Muse {result.get('model', '')}"]
    lines.append("\nCandidate hypothesis (unconfirmed):")
    candidate = result.get("candidate_finding", "")
    lines.append(f"  {candidate}" if candidate else "  No evolution established from this archive.")
    lines.append("\nObserved chronology:")
    for item in result.get("observations", []):
        lines.append(
            f"  · {item['date']} · {item['artifact_id']} · {item['evidence_stage']} — {item['observation']}"
        )
    lines.append("\nSupporting artifacts:")
    for item in result.get("supporting_artifacts", []):
        lines.append(f"  + {item['date']} · {item['artifact_id']} — {item['relevance']}")
    lines.append("\nComplicating artifacts:")
    for item in result.get("complicating_artifacts", []):
        lines.append(f"  ! {item['date']} · {item['artifact_id']} — {item['relevance']}")
    if not result.get("complicating_artifacts"):
        lines.append("  None cited.")
    lines.append(f"\nLimitations: {result.get('limitations', '')}")
    if (response := result.get("response")) is not None:
        lines.append(
            "\nModel response: "
            f"status={response.get('status') or 'unknown'}, "
            f"incomplete_reason={response.get('incomplete_reason') or 'none'}"
        )
    if (usage := result.get("usage")) is not None:
        lines.append(
            f"\nAPI usage: {usage['input_tokens']} input, {usage['output_tokens']} output tokens; "
            f"estimated ${usage['estimated_usd']:.6f}."
        )
    lines.append("\nCreator review is required before treating this as an insight.")
    return "\n".join(lines)


def _render_memories(result: dict[str, Any]) -> str:
    project = result["project"]
    lines = [f"{project['title']} · extracted temporal memories ({result['model']})"]
    for memory in result["memories"]:
        themes = ", ".join(memory["themes"]) or "no topic tags"
        lines.extend([
            f"\n{memory['date']} · {memory['modality']} · {memory['source_id']}",
            f"  {memory['summary']}",
            f"  Topics: {themes}",
        ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description="Discover one evidence-backed evolution in a creative project.")
    parser.add_argument(
        "dataset",
        nargs="?",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "datasets" / "synthetic" / "creative-evolution.json",
        help="path to a schema_version 1 JSON dataset",
    )
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON")
    parser.add_argument("--raw-muse", action="store_true", help="discover directly from raw artifacts; combine with --review for creator interview")
    parser.add_argument("--extract-memories", action="store_true", help="extract dated source-linked memories with Muse and print them without discovery")
    parser.add_argument("--review", action="store_true", help="interview and disposition a candidate; combine with --raw-muse for direct Muse discovery")
    parser.add_argument("--provider", choices=("fixture", "meta"), default="fixture", help="theme extraction source")
    args = parser.parse_args()
    if args.extract_memories and (args.review or args.raw_muse):
        parser.error("--extract-memories cannot be combined with --review or --raw-muse")

    try:
        if args.review:
            if args.json:
                parser.error("--review is interactive and cannot be combined with --json")
            from .review import review_finding
            if args.raw_muse:
                from .raw_discovery import discover_raw_archive
                from .review import adapt_raw_discovery

                raw_result = discover_raw_archive(args.dataset)
                if not raw_result.get("candidate_finding", "").strip():
                    print(_render_raw_discovery(raw_result))
                    return 0
                finding = adapt_raw_discovery(raw_result)
            else:
                from .service import discover_dataset

                finding = discover_dataset(dataset_path=args.dataset, provider_name=args.provider)
            review_finding(finding)
            return 0
        if args.extract_memories:
            from .service import extract_dataset_memories

            result = extract_dataset_memories(dataset_path=args.dataset)
        elif args.raw_muse:
            from .raw_discovery import discover_raw_archive

            result = discover_raw_archive(args.dataset)
        else:
            from .service import discover_dataset

            result = discover_dataset(dataset_path=args.dataset, provider_name=args.provider)
    except DatasetError as exc:
        print(f"thread-discover: invalid dataset [{exc.code}]: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        if str(exc).startswith("No sufficiently supported evolution finding"):
            print("No sufficiently supported evolution finding in this dataset.")
            return 0
        print(f"thread-discover: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:
        print(f"thread-discover: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if args.raw_muse:
            print(_render_raw_discovery(result))
        elif args.extract_memories:
            print(_render_memories(result))
        else:
            print(_render_text(result))
        if not args.raw_muse and (usage := result.get("api_usage")) is not None:
            print(
                "\nAPI usage this run: "
                f"{usage['requests']} requests, {usage['cache_hits']} cache hits, "
                f"estimated ${usage['estimated_usd']:.6f}; "
                f"cumulative local estimate ${usage['cumulative_estimated_usd']:.6f}."
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
