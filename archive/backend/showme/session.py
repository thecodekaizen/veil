"""Replay physical snapshot checks without treating simulation as observation.

Client retains the log; this pure reducer creates no global server-side session.
"""
from __future__ import annotations
import hashlib
import json
from typing import Any
from .observe import validate_snapshot
from .process import validate_references


def process_fingerprint(process: dict[str, Any]) -> str:
    claims = {k: v for k, v in process.items() if not k.startswith("_")}
    return hashlib.sha256(json.dumps(claims, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def reconcile_session(process: dict[str, Any], checks: list[dict[str, Any]]) -> dict[str, Any]:
    """Project a bounded ordered log of physical checks into guidance, not truth."""
    validate_references(process)
    if not isinstance(checks, list) or len(checks) > 100:
        raise ValueError("provide at most 100 physical checks")
    fingerprint = process_fingerprint(process)
    seen = set()
    previous = -1
    last_match = None
    current = None
    last_issue = None
    for check in checks:
        if not isinstance(check, dict):
            raise ValueError("physical check must be an object")
        identity = check.get("id")
        sequence = check.get("sequence")
        if not isinstance(identity, str) or not identity.strip() or identity in seen:
            raise ValueError("physical check IDs must be unique nonempty strings")
        if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence <= previous:
            raise ValueError("physical check sequence must strictly increase")
        if check.get("source") != "physical-snapshot":
            raise ValueError("simulation results cannot enter physical observation history")
        if check.get("process_sha256") != fingerprint:
            raise ValueError("physical check belongs to a different process revision")
        snapshot = check.get("observation")
        validate_snapshot(snapshot, process)
        seen.add(identity); previous = sequence
        current = None
        if snapshot["assessment"] == "consistent":
            current = {"check_id": identity, "sequence": sequence, "state_id": snapshot["state_id"],
                       "evidence": snapshot["evidence"]}
            last_match = current
        elif snapshot["assessment"] == "possible_divergence":
            last_issue = {"check_id": identity, "sequence": sequence,
                          "object_ids": snapshot["object_ids"], "evidence": snapshot["evidence"]}
    next_actions = [t for t in process["transitions"] if current and t["from_state"] == current["state_id"]]
    next_action = None
    if len(next_actions) == 1:
        transition = next_actions[0]
        next_action = {"transition_id": transition["id"], "action": transition["action"],
                       "object_ids": transition["object_ids"], "to_state": transition["to_state"],
                       "basis": "next action in reviewed trace; not a proven required order"}
    return {"process_sha256": fingerprint, "checks_count": len(checks), "current_match": current,
            "last_match": last_match, "last_reported_issue": last_issue, "next_action": next_action,
            "branch_requires_review": len(next_actions) > 1,
            "recovery_status": "unverified" if last_issue else "not_assessed",
            "completion_status": "not_assessed",
            "scope": "projection of explicit physical checks; no continuous tracking"}
