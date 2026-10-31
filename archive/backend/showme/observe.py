"""Compare a learner clip with a learned process without seeing evaluation labels."""

from __future__ import annotations

import json
import math
from pathlib import Path
import hashlib
from typing import Any

from .meta import MuseSparkClient

OBSERVATION_PROMPT_VERSION = "showme-observe-v6"


def observation_schema(process: dict[str, Any]) -> dict[str, Any]:
    state_ids = [item["id"] for item in process["states"]]
    object_ids = [item["id"] for item in process["objects"]]
    state_choices = [*state_ids, "unknown"]
    object_choices = [*object_ids, "unknown"]
    reference_transition_ids = [
        transition["id"] for transition in process["transitions"]
        if transition.get("reference_evidence")
    ] or ["none"]
    return {
        "type": "object",
        "properties": {
            "events": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "time_seconds": {"type": "number", "minimum": 0},
                        "action": {"type": "string"},
                        "state_id": {"type": "string", "enum": state_choices},
                        "assessment": {"type": "string", "enum": ["consistent", "divergent", "unclear"]},
                        "object_ids": {"type": "array", "items": {"type": "string", "enum": object_choices}},
                        "evidence": {"type": "string"},
                    },
                    "required": ["time_seconds", "action", "state_id", "assessment", "object_ids", "evidence"],
                    "additionalProperties": False,
                },
            },
            "divergences": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "time_seconds": {"type": "number", "minimum": 0},
                        "process_difference": {"type": "string"},
                        "object_ids": {"type": "array", "items": {"type": "string", "enum": object_choices}},
                        "evidence": {"type": "string"},
                    },
                    "required": ["time_seconds", "process_difference", "object_ids", "evidence"],
                    "additionalProperties": False,
                },
            },
            "recovery_status": {
                "type": "string",
                "enum": ["no_divergence_observed", "underway", "recovered", "unclear"],
            },
            "uncertainties": {"type": "array", "items": {"type": "string"}},
            "reference_checks": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "transition_id": {"type": "string", "enum": reference_transition_ids},
                        "status": {"type": "string", "enum": ["matches_reference", "possible_mismatch", "not_shown", "unclear"]},
                        "time_seconds": {"type": ["number", "null"], "minimum": 0},
                        "evidence": {"type": "string"},
                        "next_guidance": {"type": "string"},
                    },
                    "required": ["transition_id", "status", "time_seconds", "evidence", "next_guidance"],
                    "additionalProperties": False,
                },
            },
        },
        "required": ["events", "divergences", "recovery_status", "uncertainties", "reference_checks"],
        "additionalProperties": False,
    }


def observation_prompt(process: dict[str, Any], duration_seconds: float, *, has_reference: bool = False) -> str:
    clean_process = {key: value for key, value in process.items() if not key.startswith("_")}
    reference_context = (
        "The attached PDF supplies direct reference evidence. Inspect its cited page/step before comparing "
        "a source relationship; if the extracted process conflicts with the PDF, disclose the source-model "
        "conflict in uncertainties instead of diagnosing the learner from that unsupported process claim. "
    ) if has_reference else (
        "No reference PDF or expert images are attached. You can compare only the extracted process claims, "
        "not independently verify the cited manual diagrams. Disclose this limitation in uncertainties. "
    )
    return (
        reference_context +
        "Compare this learner video with the process learned from an expert. "
        "The process is a hypothesis, and the learner clip may be correct, divergent, "
        "ambiguous, or recovered; do not assume which. Do not infer unseen events. "
        "Record transient interactions with tools, parts or attachment points even when the learner later "
        "returns to the modeled trace. Do not omit an observed interaction merely because it has no matching "
        "transition or because its intent is uncertain. Give it an unclear event with state_id unknown, "
        "visible evidence and declared affected object IDs (or unknown when no declared object applies). "
        "Keep noticing an unexpected interaction separate from diagnosing a mistake: a brief selection, "
        "touch, repositioning or inspection is not automatically a procedural error. "
        "The learned clip is only one observed trace: its ordering_observations describe "
        "what happened before what in that clip, not required prerequisites. Do not call "
        "a learner divergent only because they perform those actions in another order. "
        "Report divergence only when the visible learner state conflicts with a clearly "
        "described process state; treat uncertain dependencies as uncertainty. "
        "Return time-stamped visible events in chronological order. Mark a state 'unknown' "
        "when the video cannot support a match. Use only declared state/object IDs or "
        "'unknown'. Include evidence that a reviewer can locate in the clip. Do not "
        "claim recovery unless the clip visibly returns to a process-consistent state for the same affected objects "
        "after the last divergence. Inspect visible attachment, orientation, and spatial relationships explicitly "
        "when the process describes them; do not substitute object presence for correct placement. "
        "If the process lacks an orientation rule, report that limitation rather than inventing one. "
        "A detached component establishes a different physical state, but does not by itself establish a mistake: "
        "consider partial assembly, inspection, disassembly, and recovery. Explain the observed difference "
        "without inferring the learner intent. Compare identifiable joints, connector surfaces and relative "
        "facing when visible. Apparent size in different views or diagram scales is not enough to establish "
        "a wrong part: require identifiable shape/attachment evidence or mark the comparison unclear. "
        "When a reference_check is possible_mismatch, give a divergence record at that same evidence "
        "timestamp, even if the issue persists across several events. "
        "For every transition that has reference_evidence, return exactly one reference_check using its transition ID. "
        "Use matches_reference only with direct visual evidence; use possible_mismatch only for a visible conflict "
        "with the cited manual step, and add the same issue to divergences. Use not_shown when the step is absent "
        "or the part is already assembled: do not infer it is missing. Use unclear when blur, hands, or occlusion "
        "prevent a decision. Include a timestamp for visible evidence and null when not_shown; for every status "
        "except matches_reference, give one concrete next action (perform the cited step, show the relevant joint, "
        "or correct the visible mismatch). The manual states intended steps; the learner clip shows current evidence. "
        f"All times must be in [0, {duration_seconds:.3f}) seconds.\n\n"
        f"Learned process:\n{json.dumps(clean_process, ensure_ascii=False, sort_keys=True)}"
    )


def validate_observation(
    observation: dict[str, Any], process: dict[str, Any], duration_seconds: float,
) -> None:
    """Fail closed on invented process IDs, invalid timestamps, or unsupported recovery."""
    if not isinstance(observation, dict):
        raise ValueError("observation must be an object")
    state_ids = {item["id"] for item in process["states"]}
    object_ids = {item["id"] for item in process["objects"]}
    events = observation.get("events")
    divergences = observation.get("divergences")
    if not isinstance(events, list) or not isinstance(divergences, list):
        raise ValueError("observation events and divergences must be arrays")

    prior_time = -1.0
    for index, event in enumerate(events):
        timestamp = _valid_time(event, duration_seconds, f"event {index}")
        if timestamp < prior_time:
            raise ValueError("observation events must be chronological")
        prior_time = timestamp
        if event.get("state_id") != "unknown" and event.get("state_id") not in state_ids:
            raise ValueError(f"event {index} references an unknown state_id")
        if event.get("assessment") not in {"consistent", "divergent", "unclear"}:
            raise ValueError(f"event {index} has an invalid assessment")
        if not isinstance(event.get("evidence"), str) or not event["evidence"].strip():
            raise ValueError(f"event {index} needs inspectable evidence")
        _validate_objects(event.get("object_ids"), object_ids, f"event {index}")

    divergence_times: list[float] = []
    for index, divergence in enumerate(divergences):
        divergence_times.append(_valid_time(divergence, duration_seconds, f"divergence {index}"))
        if not isinstance(divergence.get("evidence"), str) or not divergence["evidence"].strip():
            raise ValueError(f"divergence {index} needs inspectable evidence")
        _validate_objects(divergence.get("object_ids"), object_ids, f"divergence {index}")

    status = observation.get("recovery_status")
    _validate_reference_checks(observation, process, duration_seconds, divergences)
    allowed_statuses = {"no_divergence_observed", "underway", "recovered", "unclear"}
    if status not in allowed_statuses:
        raise ValueError("observation has an invalid recovery_status")
    has_divergent_event = any(event.get("assessment") == "divergent" for event in events)
    if has_divergent_event and not divergence_times:
        raise ValueError("divergent events need at least one divergence record")
    if status == "no_divergence_observed" and (divergence_times or has_divergent_event):
        raise ValueError("recovery status conflicts with reported divergences")
    if status == "recovered":
        if not divergence_times:
            raise ValueError("recovery cannot be marked without a visible divergence")
        last_divergence = max([
            *divergence_times,
            *(event["time_seconds"] for event in events if event["assessment"] == "divergent"),
        ])
        for divergence in divergences:
            affected = set(divergence["object_ids"]) - {"unknown"}
            if not affected or not any(
                event["assessment"] == "consistent"
                and event["state_id"] in state_ids
                and event["time_seconds"] > last_divergence
                and affected.issubset(set(event["object_ids"]))
                for event in events
            ):
                raise ValueError(
                    "recovery needs a later process-consistent event for each affected object "
                    "after the last divergence"
                )


def snapshot_schema(process: dict[str, Any]) -> dict[str, Any]:
    """Constrain one camera-frame assessment to the reviewed process vocabulary."""
    state_ids = [item["id"] for item in process["states"]]
    object_ids = [item["id"] for item in process["objects"]]
    return {
        "type": "object",
        "properties": {
            "state_id": {"type": "string", "enum": [*state_ids, "unknown"]},
            "assessment": {"type": "string", "enum": ["consistent", "possible_divergence", "unclear"]},
            "object_ids": {"type": "array", "items": {"type": "string", "enum": [*object_ids, "unknown"]}},
            "evidence": {"type": "string"},
            "uncertainties": {"type": "array", "items": {"type": "string"}},
            "view_guidance": {"type": "string"},
        },
        "required": ["state_id", "assessment", "object_ids", "evidence", "uncertainties", "view_guidance"],
        "additionalProperties": False,
    }


def snapshot_prompt(process: dict[str, Any]) -> str:
    clean_process = {key: value for key, value in process.items() if not key.startswith("_")}
    return (
        "Inspect this single still image from a learner's physical workspace against the reviewed process model. "
        "This is one snapshot, not a video: do not infer action order, what happened before, recovery, or intent. "
        "Use consistent only when visible facts match a declared process state. Use possible_divergence only "
        "when a visible relationship clearly conflicts with the described states; do not treat an unobserved "
        "action order as a violation. Use unclear when the relevant parts are occluded, too small, or ambiguous. "
        "Use only declared state/object IDs or unknown. Explain the visible evidence plainly, and list uncertainty. "
        "When unclear, give one concise, actionable camera/view adjustment that would help inspect the uncertain part "
        "(such as move a hand away, move closer, or show the assembly from above). Otherwise return an empty "
        "view_guidance string. Do not claim that changing the view will guarantee a conclusion. "
        f"\n\nReviewed process hypothesis:\n{json.dumps(clean_process, ensure_ascii=False, sort_keys=True)}"
    )


def validate_snapshot(snapshot: dict[str, Any], process: dict[str, Any]) -> None:
    if not isinstance(snapshot, dict):
        raise ValueError("snapshot observation must be an object")
    state_ids = {item["id"] for item in process["states"]}
    object_ids = {item["id"] for item in process["objects"]}
    state_id = snapshot.get("state_id")
    assessment = snapshot.get("assessment")
    if state_id != "unknown" and state_id not in state_ids:
        raise ValueError("snapshot references an unknown state_id")
    if assessment not in {"consistent", "possible_divergence", "unclear"}:
        raise ValueError("snapshot has an invalid assessment")
    if assessment == "consistent" and state_id == "unknown":
        raise ValueError("a consistent snapshot must match a declared state")
    if not isinstance(snapshot.get("evidence"), str) or not snapshot["evidence"].strip():
        raise ValueError("snapshot needs inspectable evidence")
    view_guidance = snapshot.get("view_guidance")
    if not isinstance(view_guidance, str):
        raise ValueError("snapshot view_guidance must be a string")
    if assessment == "unclear" and not view_guidance.strip():
        raise ValueError("unclear snapshots need actionable view_guidance")
    _validate_objects(snapshot.get("object_ids"), object_ids, "snapshot")
    uncertainties = snapshot.get("uncertainties")
    if not isinstance(uncertainties, list) or not all(isinstance(item, str) for item in uncertainties):
        raise ValueError("snapshot uncertainties must be an array of strings")


def observe_snapshot(
    learner: MuseSparkClient,
    image_path: Any,
    process: dict[str, Any],
) -> dict[str, Any]:
    return learner.analyze_image(
        image_path,
        prompt=snapshot_prompt(process),
        schema=snapshot_schema(process),
        schema_name="showme_snapshot_observation",
        max_output_tokens=1000,
    )


def _valid_time(item: Any, duration: float, label: str) -> float:
    if not isinstance(item, dict):
        raise ValueError(f"{label} must be an object")
    timestamp = item.get("time_seconds")
    if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
        raise ValueError(f"{label} time_seconds must be numeric")
    if not math.isfinite(timestamp) or not 0 <= timestamp < duration:
        raise ValueError(f"{label} time_seconds must be within the clip")
    return float(timestamp)


def _validate_objects(value: Any, object_ids: set[str], label: str) -> None:
    if not isinstance(value, list):
        raise ValueError(f"{label} object_ids must be an array")
    for object_id in value:
        if object_id != "unknown" and object_id not in object_ids:
            raise ValueError(f"{label} references an unknown object_id")


def _validate_reference_checks(
    observation: dict[str, Any], process: dict[str, Any], duration: float, divergences: list[Any],
) -> None:
    expected = {
        transition["id"] for transition in process["transitions"]
        if transition.get("reference_evidence")
    }
    checks = observation.get("reference_checks")
    if not isinstance(checks, list):
        raise ValueError("reference_checks must be an array")
    seen: set[str] = set()
    for index, check in enumerate(checks):
        if not isinstance(check, dict):
            raise ValueError(f"reference check {index} must be an object")
        transition_id = check.get("transition_id")
        if not isinstance(transition_id, str) or transition_id not in expected:
            raise ValueError(f"reference check {index} references an unexpected transition")
        if transition_id in seen:
            raise ValueError("reference_checks must contain each reference transition exactly once")
        seen.add(transition_id)
        status = check.get("status")
        if not isinstance(status, str) or status not in {"matches_reference", "possible_mismatch", "not_shown", "unclear"}:
            raise ValueError(f"reference check {index} has an invalid status")
        evidence = check.get("evidence")
        guidance = check.get("next_guidance")
        if not isinstance(evidence, str) or not evidence.strip():
            raise ValueError(f"reference check {index} needs evidence")
        if not isinstance(guidance, str):
            raise ValueError(f"reference check {index} next_guidance must be a string")
        timestamp = check.get("time_seconds")
        if timestamp is None:
            if status in {"matches_reference", "possible_mismatch"}:
                raise ValueError(f"reference check {index} needs a timestamp for visible evidence")
        else:
            if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)):
                raise ValueError(f"reference check {index} time_seconds must be numeric or null")
            if not math.isfinite(timestamp) or not 0 <= timestamp < duration:
                raise ValueError(f"reference check {index} time_seconds must be within the clip")
            if status == "not_shown":
                raise ValueError(f"reference check {index} must use a null timestamp when not_shown")
        if status != "matches_reference" and not guidance.strip():
            raise ValueError(f"reference check {index} needs actionable next_guidance")
        if status == "possible_mismatch" and not any(
            abs(float(item["time_seconds"]) - float(timestamp)) <= 2.0
            for item in divergences
        ):
            raise ValueError("possible reference mismatches need a divergence record at the same evidence time")
    if seen != expected:
        raise ValueError("reference_checks must contain each reference transition exactly once")


def observe_video(
    learner: MuseSparkClient,
    video_path: Any,
    process: dict[str, Any],
    duration_seconds: float,
    *,
    reference_pdf: Path | None = None,
) -> dict[str, Any]:
    has_references = any(item.get("reference_evidence") for item in process["transitions"])
    reference_metadata = None
    if reference_pdf is not None:
        reference_pdf = reference_pdf.expanduser().resolve()
        if not reference_pdf.is_file() or reference_pdf.read_bytes()[:5] != b"%PDF-":
            raise ValueError("task reference must be a readable PDF")
        reference_metadata = {"sha256": hashlib.sha256(reference_pdf.read_bytes()).hexdigest()}
    options = {"reference_pdf": reference_pdf} if reference_pdf is not None else {}
    observation = learner.analyze_video(
        video_path,
        prompt=observation_prompt(process, duration_seconds, has_reference=reference_pdf is not None),
        schema=observation_schema(process),
        schema_name="showme_learner_observation",
        max_output_tokens=4500 if has_references else 2500,
        **options,
    )
    observation.setdefault("_run", {})["prompt_version"] = OBSERVATION_PROMPT_VERSION
    # Fingerprint exactly the semantic process sent in the prompt; private run metadata is excluded.
    clean_process = {key: value for key, value in process.items() if not key.startswith("_")}
    observation["_run"]["process_sha256"] = hashlib.sha256(
        json.dumps(clean_process, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()
    observation["_run"]["comparison_source"] = "attached_reference" if reference_pdf else "extracted_process_only"
    observation["_run"]["reference_document"] = reference_metadata
    return observation
