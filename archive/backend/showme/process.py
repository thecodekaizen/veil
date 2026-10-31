"""Structured contract for a process proposed from a demonstration video."""

from __future__ import annotations

import math
from typing import Any


PROCESS_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "task_summary": {"type": "string"},
        "objects": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "label": {"type": "string"},
                    "visual_description": {"type": "string"},
                },
                "required": ["id", "label", "visual_description"],
                "additionalProperties": False,
            },
        },
        "states": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "description": {"type": "string"},
                    "observable_facts": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "description", "observable_facts"],
                "additionalProperties": False,
            },
        },
        "transitions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "from_state": {"type": "string"},
                    "action": {"type": "string"},
                    "object_ids": {"type": "array", "items": {"type": "string"}},
                    "to_state": {"type": "string"},
                    "candidate_constraints": {
                        "type": "array",
                        "description": "Unverified model hypotheses only. One demonstration cannot establish that a condition is required.",
                        "items": {"type": "string"},
                    },
                    "postconditions": {"type": "array", "items": {"type": "string"}},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "start_seconds": {"type": "number", "minimum": 0},
                                "end_seconds": {"type": "number", "minimum": 0},
                                "observation": {"type": "string"},
                            },
                            "required": ["start_seconds", "end_seconds", "observation"],
                            "additionalProperties": False,
                        },
                    },
                    "reference_evidence": {
                        "type": "array",
                        "description": "Citations to task instructions that support intended steps; empty when no reference PDF is supplied.",
                        "items": {
                            "type": "object",
                            "properties": {
                                "page": {"type": "integer", "minimum": 1},
                                "step": {"type": "string"},
                                "observation": {"type": "string"},
                            },
                            "required": ["page", "step", "observation"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["id", "from_state", "action", "object_ids", "to_state", "candidate_constraints", "postconditions", "evidence", "reference_evidence"],
                "additionalProperties": False,
            },
        },
        "ordering_observations": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "before_transition_id": {"type": "string"},
                    "after_transition_id": {"type": "string"},
                    "evidence": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "start_seconds": {"type": "number", "minimum": 0},
                                "end_seconds": {"type": "number", "minimum": 0},
                                "observation": {"type": "string"},
                            },
                            "required": ["start_seconds", "end_seconds", "observation"],
                            "additionalProperties": False,
                        },
                    },
                },
                "required": ["before_transition_id", "after_transition_id", "evidence"],
                "additionalProperties": False,
            },
        },
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["task_summary", "objects", "states", "transitions", "ordering_observations", "uncertainties"],
    "additionalProperties": False,
}


def validate_references(process: dict[str, Any], *, duration_seconds: float | None = None) -> None:
    """Reject duplicate IDs and transitions pointing to undefined entities."""
    if not isinstance(process, dict):
        raise ValueError("process must be an object")
    objects = process.get("objects")
    states = process.get("states")
    transitions = process.get("transitions")
    if not isinstance(objects, list) or not isinstance(states, list) or not isinstance(transitions, list):
        raise ValueError("process objects, states, and transitions must be arrays")

    object_ids = _unique_ids(objects, "object")
    state_ids = _unique_ids(states, "state")
    transition_ids = _unique_ids(transitions, "transition")
    for index, transition in enumerate(transitions):
        label = f"transition {index}"
        if not isinstance(transition, dict):
            raise ValueError(f"{label} must be an object")
        for field in ("from_state", "to_state"):
            state_id = transition.get(field)
            if state_id not in state_ids:
                raise ValueError(f"{label} references unknown {field} {state_id!r}")
        references = transition.get("object_ids")
        if not isinstance(references, list):
            raise ValueError(f"{label} object_ids must be an array")
        for object_id in references:
            if object_id not in object_ids:
                raise ValueError(f"{label} references unknown object_id {object_id!r}")
        evidence = transition.get("evidence")
        reference_evidence = transition.get("reference_evidence")
        if not isinstance(evidence, list) or not isinstance(reference_evidence, list):
            raise ValueError(f"{label} evidence fields must be arrays")
        if not evidence and not reference_evidence:
            raise ValueError(f"{label} needs video or reference evidence")
        if evidence:
            _validate_evidence(evidence, label, duration_seconds)
        for reference_index, item in enumerate(reference_evidence):
            reference_label = f"{label} reference evidence {reference_index}"
            if not isinstance(item, dict):
                raise ValueError(f"{reference_label} must be an object")
            page = item.get("page")
            if isinstance(page, bool) or not isinstance(page, int) or page < 1:
                raise ValueError(f"{reference_label} page must be a positive integer")
            for field in ("step", "observation"):
                value = item.get(field)
                if not isinstance(value, str) or not value.strip():
                    raise ValueError(f"{reference_label} needs a {field}")

    ordering_observations = process.get("ordering_observations")
    if not isinstance(ordering_observations, list):
        raise ValueError("process ordering_observations must be an array")
    for index, relation in enumerate(ordering_observations):
        label = f"ordering observation {index}"
        if not isinstance(relation, dict):
            raise ValueError(f"{label} must be an object")
        before = relation.get("before_transition_id")
        after = relation.get("after_transition_id")
        if before not in transition_ids:
            raise ValueError(f"{label} references unknown before_transition_id {before!r}")
        if after not in transition_ids:
            raise ValueError(f"{label} references unknown after_transition_id {after!r}")
        if before == after:
            raise ValueError(f"{label} must refer to two different transitions")
        _validate_evidence(relation.get("evidence"), label, duration_seconds)


def _validate_evidence(evidence: Any, label: str, duration_seconds: float | None) -> None:
    if not isinstance(evidence, list) or not evidence:
        raise ValueError(f"{label} needs at least one evidence interval")
    for evidence_index, item in enumerate(evidence):
        evidence_label = f"{label} evidence {evidence_index}"
        if not isinstance(item, dict):
            raise ValueError(f"{evidence_label} must be an object")
        start = item.get("start_seconds")
        end = item.get("end_seconds")
        for field, value in (("start_seconds", start), ("end_seconds", end)):
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                raise ValueError(f"{evidence_label} {field} must be finite and numeric")
        if start < 0 or end < start:
            raise ValueError(f"{evidence_label} must be a non-negative, ordered interval")
        if duration_seconds is not None and end > duration_seconds:
            raise ValueError(f"{evidence_label} ends outside the expert clip")
        observation = item.get("observation")
        if not isinstance(observation, str) or not observation.strip():
            raise ValueError(f"{evidence_label} needs a visible observation")


def _unique_ids(items: list[Any], kind: str) -> set[str]:
    ids: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"{kind} {index} must be an object")
        identifier = item.get("id")
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError(f"{kind} {index} must have a non-empty id")
        if identifier in ids:
            raise ValueError(f"duplicate {kind} id {identifier!r}")
        ids.add(identifier)
    return ids
