"""Turn validated joint evidence into bounded, source-linked intervention."""
from __future__ import annotations
from typing import Any
from .focus import validate_inspection
from .joint_recovery import assess_recovery
from .process import validate_references
from .session import process_fingerprint


def build_guidance(process: dict[str, Any], report: dict[str, Any], report_kind: str) -> dict[str, Any]:
    validate_references(process)
    if not isinstance(report, dict) or not isinstance(report.get("_run"), dict):
        raise ValueError("guidance requires a provenance-linked report")
    run = report["_run"]
    if run.get("process_sha256") != process_fingerprint(process):
        raise ValueError("report does not match the reviewed process revision")
    transition_id = run.get("transition_id")
    transition = next((t for t in process["transitions"] if t["id"] == transition_id), None)
    if transition is None:
        raise ValueError("report refers to an undeclared transition")
    if report_kind == "joint-inspection":
        validate_inspection(report, process, transition_id, relationship_target=run.get("relationship_target", "all"))
        status = report["assessment"]
        if status == "matches":
            decision, message = "continue_observing", "The reported joint relationships match. Other parts and later changes remain unchecked."
        elif status == "possible_difference":
            decision, message = "review_difference", "Inspect the reported contact or facing difference against the source before changing the assembly."
        else:
            decision, message = "request_view", report["view_guidance"]
    elif report_kind == "joint-recovery":
        status = assess_recovery(report, process, transition_id)
        if report.get("status") != status:
            raise ValueError("recovery status conflicts with relationship evidence")
        if status == "recovery_reported":
            decision, message = "review_reported_recovery", "The same joint is reported to match after a visible difference. Review both observations; task completion is not established."
        elif status == "current_difference_reported":
            decision, message = "review_difference", "A contact or facing difference remains reported. Inspect the source and latest evidence."
        elif status == "no_prior_difference_reported":
            decision, message = "continue_observing", "No prior difference was established; matching views alone are not a recovery."
        else:
            decision, message = "request_view", report["view_guidance"]
    else:
        raise ValueError("unsupported guidance report kind")
    affected = sorted({i for relation in report["relations"] for i in relation["object_ids"]})
    objects = [item for item in process["objects"] if item["id"] in affected]
    target = next(item for item in process["states"] if item["id"] == transition["to_state"])
    return {"decision": decision, "message": message, "assessment": status,
        "affected_objects": objects, "transition_id": transition_id,
        "modeled_action": {"label": transition["action"], "basis": "reviewed process; not an inferred repair"},
        "expected_state": {"id": target["id"], "description": target["description"], "observable_facts": target["observable_facts"]},
        "evidence": {"video": transition.get("evidence", []), "reference": transition.get("reference_evidence", []),
                     "reported_relations": report["relations"]},
        "repair_steps": [], "repair_status": "not_established",
        "process_sha256": run["process_sha256"], "scope": "source-linked guidance over reported evidence, no automatic physical intervention"}
