"""Interactive local review and confirmation gate for a discovery candidate."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Callable
from uuid import uuid4

REPO_OUTPUT_DIR = Path(__file__).resolve().parents[2] / ".thread-output"


def adapt_raw_discovery(raw: dict) -> dict:
    """Adapt a validated raw Muse result to the creator-review contract."""
    candidate = raw.get("candidate_finding", "").strip()
    if not candidate:
        raise ValueError("raw discovery has no candidate to review")
    project = raw.get("project", {})

    def evidence(items: list[dict]) -> list[dict]:
        return [
            {
                "source_id": item["artifact_id"],
                "date": item["date"],
                "summary": item["relevance"],
                "theme": "raw source",
            }
            for item in items
        ]

    candidate_id = hashlib.sha256(
        f"{project.get('id', '')}\0{candidate}".encode("utf-8")
    ).hexdigest()[:16]
    return {
        "id": f"raw-{candidate_id}",
        "project_title": project.get("title", "Project"),
        "hypothesis": candidate,
        "supporting_evidence": evidence(raw.get("supporting_artifacts", [])),
        "counter_evidence": evidence(raw.get("complicating_artifacts", [])),
        "continuity_evidence": [],
        "observations": [
            {
                "source_id": item["artifact_id"],
                "date": item["date"],
                "summary": item["observation"],
                "evidence_stage": item["evidence_stage"],
            }
            for item in raw.get("observations", [])
        ],
        "uncertainty": [raw["limitations"]] if raw.get("limitations") else [],
        "discovery_mode": "raw",
        "extraction_provider": raw.get("provider", "meta"),
        "extraction_model": raw.get("model", "model unknown"),
        "response": raw.get("response", {}),
        "usage": raw.get("usage", {}),
    }


def _validate_answer(value: str, label: str) -> str:
    answer = value.strip()
    if len(answer) < 12:
        raise ValueError(f"{label} must contain at least 12 non-space characters")
    return answer


def _write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def review_finding(
    finding: dict,
    *,
    ask: Callable[[str], str] = input,
    emit: Callable[[str], None] = print,
    output_dir: Path = REPO_OUTPUT_DIR,
) -> dict:
    """Interview the creator, require an explicit confirmation, and write a note.

    User answers and generated outputs stay in the ignored local output directory.
    An artifact is written only after the creator types the exact confirmation word.
    """
    if not finding.get("hypothesis") or not finding.get("supporting_evidence"):
        raise ValueError("review requires a supported discovery finding")

    session_id = str(uuid4())
    session_path = output_dir / "sessions" / f"{session_id}.json"
    state = {
        "session_id": session_id,
        "stage": "discovered",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "finding": finding,
        "answers": [],
        "artifact_path": None,
    }

    def save() -> None:
        session_path.parent.mkdir(parents=True, exist_ok=True)
        _write_json(session_path, state)

    def response(question: str, label: str) -> str:
        while True:
            try:
                return _validate_answer(ask(question), label)
            except ValueError as exc:
                emit(str(exc))

    save()
    if finding.get("discovery_mode") == "raw":
        response_status = finding.get("response", {}).get("status") or "unknown"
        emit(
            f"\nDirect raw discovery: Meta Model API · {finding.get('extraction_model', 'model unknown')} "
            f"(response {response_status})"
        )
        usage = finding.get("usage", {})
        if usage:
            emit(
                f"API usage: {usage.get('input_tokens', 0)} input, "
                f"{usage.get('output_tokens', 0)} output tokens; "
                f"estimated ${usage.get('estimated_usd', 0):.6f} this run; "
                f"${usage.get('cumulative_estimated_usd', 0):.6f} cumulative."
            )
    elif finding.get("extraction_provider") == "meta":
        emit(f"\nMemory extraction: Meta Model API · {finding.get('extraction_model', 'model unknown')}")
        usage = finding.get("api_usage", {})
        emit(
            f"API usage: {usage.get('requests', 0)} new request(s), "
            f"{usage.get('cache_hits', 0)} cache hit(s), "
            f"estimated ${usage.get('estimated_usd', 0):.6f} this run; "
            f"${usage.get('cumulative_estimated_usd', 0):.6f} cumulative."
        )
    emit("\nTHREAD found a candidate evolution. Review it before accepting it:")
    emit(f"\n{finding['hypothesis']}")
    emit("\nSupporting evidence:")
    for item in finding["supporting_evidence"]:
        emit(f"  + {item['date']} · {item['source_id']} — {item['summary']}")
    if finding.get("counter_evidence"):
        emit("\nCounter-evidence:")
        for item in finding["counter_evidence"]:
            emit(f"  ! {item['date']} · {item['source_id']} — {item['summary']}")
    if finding.get("continuity_evidence"):
        emit("\nContinuity evidence:")
        for item in finding["continuity_evidence"]:
            emit(f"  = {item['date']} · {item['source_id']} — {item['theme']}")
    if finding.get("observations"):
        emit("\nObserved chronology (source-stage labels are model classified):")
        for item in finding["observations"]:
            emit(
                f"  · {item['date']} · {item['source_id']} · {item['evidence_stage']} — {item['summary']}"
            )
    for caveat in finding.get("uncertainty", []):
        emit(f"  ? {caveat}")

    first_question = (
        "What context from your work supports, complicates, or changes this interpretation? "
        "Include concrete context (at least 12 characters): "
    )
    state["answers"].append(response(first_question, "Your context"))
    state["stage"] = "interviewing"
    save()

    second_question = (
        "What part of the earlier direction should remain important in the later work? "
        "If none, explain why (at least 12 characters): "
    )
    state["answers"].append(response(second_question, "Your follow-up"))
    state["stage"] = "challenged"
    state["context"] = state["answers"]
    save()

    emit("\nDisposition: keep, revise, reject, or defer this candidate.")
    while True:
        disposition = ask("Choose keep / revise / reject / defer: ").strip().lower()
        if disposition in {"keep", "revise", "reject", "defer"}:
            break
        emit("Enter keep, revise, reject, or defer.")
    state["disposition"] = disposition
    if disposition in {"reject", "defer"}:
        state["stage"] = "rejected" if disposition == "reject" else "deferred"
        save()
        outcome = "rejected" if disposition == "reject" else "deferred"
        emit(f"Candidate {outcome}. No artifact was created.")
        return state

    interpretation = finding["hypothesis"]
    if disposition == "revise":
        interpretation = response(
            "Write your revised interpretation (at least 12 characters): ",
            "Your interpretation",
        )
    state["interpretation"] = interpretation
    state["stage"] = "awaiting-confirmation"
    save()
    emit("\nFinal interpretation to confirm:")
    emit(interpretation)
    confirmation = ask("Type CONFIRM to save this insight and create its direction note: ").strip()
    if confirmation != "CONFIRM":
        state["stage"] = "unconfirmed"
        save()
        emit("Left unconfirmed. No artifact was created.")
        return state

    insight_id = f"insight-{uuid4()}"
    state["stage"] = "confirmed"
    state["insight_id"] = insight_id
    save()

    supporting = finding["supporting_evidence"]
    continuity = finding.get("continuity_evidence", [])
    counter = finding.get("counter_evidence", [])
    observations = finding.get("observations", [])
    all_evidence = [*supporting, *counter, *continuity, *observations]
    unique_sources = list(dict.fromkeys(item["source_id"] for item in all_evidence))
    artifact = {
        "title": f"{finding['project_title']} — direction note",
        "kind": "direction-note",
        "based_on_insight": insight_id,
        "candidate_id": finding["id"],
        "body": _direction_note(finding, interpretation, state["answers"], insight_id),
        "source_ids": unique_sources,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"direction-note-{insight_id.removeprefix('insight-')}.md"
    artifact_path.write_text(artifact["body"], encoding="utf-8")
    state["artifact"] = artifact
    state["artifact_path"] = str(artifact_path)
    state["stage"] = "artifact-created"
    save()
    emit(f"\nConfirmed insight saved. Direction note: {artifact_path}")
    return state


def _direction_note(finding: dict, interpretation: str, answers: list[str], insight_id: str) -> str:
    sections = [
        f"# {finding['project_title']} — direction note",
        "",
        f"**Confirmed insight:** {insight_id}",
        "",
        "## Creator-confirmed interpretation",
        "",
        interpretation,
        "",
        "## Original candidate",
        "",
        finding["hypothesis"],
        "",
        "## Creator context",
        "",
        f"- {answers[0]}",
        f"- {answers[1]}",
        "",
        "## Evidence",
        "",
    ]
    for heading, key in (
        ("Supporting", "supporting_evidence"),
        ("Counter", "counter_evidence"),
        ("Continuity", "continuity_evidence"),
    ):
        items = finding.get(key, [])
        if items:
            sections.extend([f"### {heading}", ""])
            sections.extend(
                f"- {item['date']} · `{item['source_id']}` ({item.get('theme', 'source')}) — {item['summary']}"
                for item in items
            )
            sections.append("")
    observations = finding.get("observations", [])
    if observations:
        sections.extend(["## Observed chronology", ""])
        sections.extend(
            f"- {item['date']} · `{item['source_id']}` [{item['evidence_stage']}] — {item['summary']}"
            for item in observations
        )
        sections.append("")
    limitations = finding.get("uncertainty", [])
    if limitations:
        sections.extend(["## Limitations", ""])
        sections.extend(f"- {item}" for item in limitations)
        sections.append("")
    sources = list(dict.fromkeys(
        item["source_id"]
        for key in ("supporting_evidence", "counter_evidence", "continuity_evidence", "observations")
        for item in finding.get(key, [])
    ))
    sections.extend([f"**Sources:** {', '.join(f'`{source}`' for source in sources)}", ""])
    return "\n".join(sections)
