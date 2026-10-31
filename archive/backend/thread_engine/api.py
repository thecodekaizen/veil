"""Local API for the demo's discover → challenge → confirm → create flow."""

from __future__ import annotations

import os
from typing import Literal
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .service import DEFAULT_DATASET, ProviderName, discover_dataset

app = FastAPI(title="THREAD local demo API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)
sessions: dict[str, dict] = {}


class DiscoverRequest(BaseModel):
    provider: ProviderName = "fixture"


class ChallengeRequest(BaseModel):
    answer: str = Field(min_length=12, max_length=1200)


class ConfirmRequest(BaseModel):
    interpretation: str = Field(min_length=12, max_length=600)


class ArtifactRequest(BaseModel):
    kind: Literal["direction-note"] = "direction-note"


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "thread"}


@app.post("/api/discover")
def discover(request: DiscoverRequest) -> dict:
    try:
        finding = discover_dataset(
            dataset_path=DEFAULT_DATASET,
            provider_name=request.provider,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    session_id = str(uuid4())
    first_question = (
        f"The later work leads with {finding['later_theme']}, while its prototype still keeps "
        f"{finding['earlier_theme']}. What changed in the project, and what original need still matters?"
    )
    sessions[session_id] = {
        "finding": finding,
        "stage": "discovered",
        "questions": [first_question],
        "answers": [],
    }
    return {
        "session_id": session_id,
        "stage": "discovered",
        "finding": finding,
        "first_question": first_question,
    }


def _session(session_id: str) -> dict:
    state = sessions.get(session_id)
    if state is None:
        raise HTTPException(status_code=404, detail="This local demo session has expired. Start discovery again.")
    return state


@app.post("/api/sessions/{session_id}/challenge")
def challenge(session_id: str, request: ChallengeRequest) -> dict:
    state = _session(session_id)
    expected_stage = "discovered" if not state["answers"] else "interviewing"
    if state.get("stage") != expected_stage:
        raise HTTPException(status_code=409, detail="Answer the current interview question before continuing.")
    answer = request.answer.strip()
    if len(answer) < 12:
        raise HTTPException(status_code=422, detail="Add at least 12 non-space characters to your answer.")
    answers = state["answers"]
    if len(answers) >= 2:
        raise HTTPException(status_code=409, detail="This interview is complete. Continue to your interpretation.")
    answers.append(answer)
    if len(answers) == 1:
        quote = answer[:140].rstrip()
        followup = (
            f"You said, “{quote}”. Looking at the final story-map prototype, what should a first-time visitor "
            f"encounter first, and what should {state['finding']['earlier_theme']} still help them do?"
        )
        state["questions"].append(followup)
        state["stage"] = "interviewing"
        return {"session_id": session_id, "stage": state["stage"], "next_question": followup}

    context = "\n\n".join(
        f"Q: {question}\nA: {answer}"
        for question, answer in zip(state["questions"], answers, strict=True)
    )
    state["context"] = context
    state["stage"] = "challenged"
    return {"session_id": session_id, "stage": state["stage"], "context": context}


@app.post("/api/sessions/{session_id}/confirm")
def confirm(session_id: str, request: ConfirmRequest) -> dict:
    state = _session(session_id)
    if state.get("stage") != "challenged":
        raise HTTPException(status_code=409, detail="Add your context before confirming this interpretation.")
    interpretation = request.interpretation.strip()
    if len(interpretation) < 12:
        raise HTTPException(status_code=422, detail="Add at least 12 non-space characters to your interpretation.")
    state["interpretation"] = interpretation
    state["stage"] = "confirmed"
    return {"session_id": session_id, "stage": state["stage"], "interpretation": state["interpretation"]}


@app.post("/api/sessions/{session_id}/artifact")
def create_artifact(session_id: str, request: ArtifactRequest) -> dict:
    state = _session(session_id)
    if state.get("stage") != "confirmed":
        raise HTTPException(status_code=409, detail="Confirm the interpretation before creating an artifact.")
    finding = state["finding"]
    evidence = finding["supporting_evidence"]
    sources = ", ".join(dict.fromkeys(item["source_id"] for item in evidence))
    artifact = {
        "title": f"{finding['project_title']} — direction note",
        "kind": request.kind,
        "body": (
            f"Confirmed direction\n{state['interpretation']}\n\n"
            f"Evidence to keep in view\n{finding['hypothesis']}\n"
            f"Sources: {sources}\n\n"
            f"Creator context\n{state['context']}"
        ),
        "source_ids": list(dict.fromkeys(item["source_id"] for item in evidence)),
        "based_on_insight": finding["id"],
    }
    state["stage"] = "artifact-created"
    state["artifact"] = artifact
    return {"session_id": session_id, "stage": state["stage"], "artifact": artifact}
