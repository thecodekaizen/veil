"""Local HTTP bridge for Teach's evidence-linked video learning flow."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Annotated
import json

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from .focus import inspect_joint
from .joint_recovery import compare_recovery
from .guidance import build_guidance
from .media import inspect_video, make_model_video
from .meta import MuseSparkClient
from .observe import observe_snapshot, observe_video, validate_observation, validate_snapshot
from .process import validate_references
from .sam import segment_image
from .session import reconcile_session

MAX_UPLOAD_BYTES = 100 * 1024 * 1024
MAX_SNAPSHOT_BYTES = 5 * 1024 * 1024
ALLOWED_SUFFIXES = {".mp4", ".mov", ".m4v", ".webm"}

app = FastAPI(title="SHOWME local skill API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok", "service": "showme"}


@app.post("/api/skills/learn")
def learn_skill(
    video: Annotated[UploadFile, File(description="Short demonstration video")],
    narration: Annotated[str, Form(max_length=4000)] = "",
    reference_pdf: Annotated[UploadFile | None, File(description="Optional authoritative task instructions PDF")] = None,
) -> dict:
    """Create a candidate process from a video and optional instruction PDF."""
    suffix = Path(video.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="Choose an MP4, MOV, M4V, or WebM video.")
    if not os.environ.get("MODEL_API_KEY") and not _repo_key_exists():
        raise HTTPException(status_code=503, detail="Set MODEL_API_KEY in the repository's local .env file first.")

    try:
        with tempfile.TemporaryDirectory(prefix="showme-teach-") as temporary:
            root = Path(temporary)
            source = root / f"demonstration{suffix}"
            size = _copy_bounded(video, source)
            if size == 0:
                raise ValueError("The selected video is empty.")

            reference_path = None
            reference_name = None
            if reference_pdf is not None:
                reference_name = Path(reference_pdf.filename or "instructions.pdf").name
                if Path(reference_name).suffix.lower() != ".pdf":
                    raise HTTPException(status_code=415, detail="Choose a PDF for the task instructions.")
                if reference_pdf.content_type not in {"application/pdf", "application/octet-stream"}:
                    raise HTTPException(status_code=415, detail="The task reference must be a PDF.")
                reference_path = root / "reference.pdf"
                reference_size = _copy_bounded(reference_pdf, reference_path)
                if reference_size == 0 or reference_path.read_bytes()[:5] != b"%PDF-":
                    raise ValueError("The task reference is not a readable PDF.")

            metadata = inspect_video(source)
            model_video = root / "model-input.mp4"
            model_metadata = make_model_video(source, model_video)
            process = MuseSparkClient.from_env().learn(
                model_video,
                duration_seconds=metadata["duration_seconds"],
                narration=narration,
                reference_pdf=reference_path,
            )
            validate_references(process, duration_seconds=metadata["duration_seconds"])

            # Keep the browser response useful and auditable; don't expose remote
            # provider file IDs that have already been deleted by the adapter.
            run = process.get("_run", {})
            process["_run"] = {
                "model": run.get("model"),
                "prompt_version": run.get("prompt_version"),
                "usage": run.get("usage", {}),
                "reference_filename": reference_name,
                "source": {
                    "filename": Path(video.filename or "demonstration").name,
                    "size_bytes": size,
                    "duration_seconds": metadata["duration_seconds"],
                    "width": metadata["width"],
                    "height": metadata["height"],
                    "audio_present": metadata["audio_present"],
                },
                "model_video": model_metadata,
            }
            process["_validation"] = "passed"
            return {"process": process, "status": "candidate-needs-human-review"}
    except (OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        video.file.close()
        if reference_pdf is not None:
            reference_pdf.file.close()


@app.post("/api/skills/observe")
def observe_learner(
    video: Annotated[UploadFile, File(description="Learner attempt video")],
    process_json: Annotated[str, Form(max_length=100_000)],
    reference_pdf: Annotated[UploadFile | None, File(description="Optional reference PDF sent with learner video")] = None,
) -> dict:
    """Compare a learner clip against the reviewed candidate process."""
    suffix = _validate_video(video)
    if not os.environ.get("MODEL_API_KEY") and not _repo_key_exists():
        raise HTTPException(status_code=503, detail="Set MODEL_API_KEY in the repository's local .env file first.")
    try:
        process = json.loads(process_json)
        if not isinstance(process, dict):
            raise ValueError("The reviewed process must be a JSON object.")
        source_duration = process.get("_run", {}).get("source", {}).get("duration_seconds")
        validate_references(process, duration_seconds=source_duration)

        with tempfile.TemporaryDirectory(prefix="showme-do-") as temporary:
            root = Path(temporary)
            source = root / f"learner{suffix}"
            size = _copy_bounded(video, source)
            if size == 0:
                raise ValueError("The selected learner video is empty.")

            reference_path = None
            if reference_pdf is not None:
                if Path(reference_pdf.filename or "").suffix.lower() != ".pdf" or reference_pdf.content_type not in {"application/pdf", "application/octet-stream"}:
                    raise HTTPException(status_code=415, detail="Choose a PDF for the task instructions.")
                reference_path = root / "reference.pdf"
                reference_size = _copy_bounded(reference_pdf, reference_path)
                if reference_size == 0 or reference_path.read_bytes()[:5] != b"%PDF-":
                    raise ValueError("The task reference is not a readable PDF.")

            metadata = inspect_video(source)
            model_video = root / "model-input.mp4"
            model_metadata = make_model_video(source, model_video)
            observation = observe_video(
                MuseSparkClient.from_env(),
                model_video,
                process,
                metadata["duration_seconds"],
                reference_pdf=reference_path,
            )
            validate_observation(observation, process, metadata["duration_seconds"])
            run = observation.get("_run", {})
            observation["_run"] = {
                "model": run.get("model"),
                "prompt_version": run.get("prompt_version"),
                "usage": run.get("usage", {}),
                "process_sha256": run.get("process_sha256"),
                "comparison_source": run.get("comparison_source"),
                "reference_document": run.get("reference_document"),
            }
            return {
                "observation": observation,
                "status": observation["recovery_status"],
                "source": {
                    "filename": Path(video.filename or "learner").name,
                    "size_bytes": size,
                    "duration_seconds": metadata["duration_seconds"],
                },
                "model_video": model_metadata,
            }
    except (OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        video.file.close()
        if reference_pdf is not None:
            reference_pdf.file.close()


@app.post("/api/skills/observe-snapshot")
def observe_learner_snapshot(
    image: Annotated[UploadFile, File(description="One JPEG camera snapshot")],
    process_json: Annotated[str, Form(max_length=100_000)],
) -> dict:
    """Assess one explicitly requested camera frame; this is not continuous tracking."""
    suffix = Path(image.filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg"} or image.content_type not in {"image/jpeg", "image/jpg"}:
        raise HTTPException(status_code=415, detail="Capture a JPEG snapshot from the camera preview.")
    if not os.environ.get("MODEL_API_KEY") and not _repo_key_exists():
        raise HTTPException(status_code=503, detail="Set MODEL_API_KEY in the repository's local .env file first.")
    try:
        process = json.loads(process_json)
        if not isinstance(process, dict):
            raise ValueError("The reviewed process must be a JSON object.")
        validate_references(process)
        with tempfile.TemporaryDirectory(prefix="showme-snapshot-") as temporary:
            image_path = Path(temporary) / "snapshot.jpg"
            size = _copy_bounded(image, image_path, max_bytes=MAX_SNAPSHOT_BYTES)
            if size == 0:
                raise ValueError("The camera snapshot is empty.")
            observation = observe_snapshot(MuseSparkClient.from_env(), image_path, process)
            validate_snapshot(observation, process)
            run = observation.get("_run", {})
            observation["_run"] = {
                "model": run.get("model"),
                "prompt_version": run.get("prompt_version"),
                "usage": run.get("usage", {}),
            }
            return {"observation": observation, "status": observation["assessment"]}
    except (OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        image.file.close()


@app.post("/api/skills/ground-object")
def ground_snapshot_object(
    image: Annotated[UploadFile, File(description="The same JPEG camera snapshot previously checked")],
    process_json: Annotated[str, Form(max_length=100_000)],
    object_id: Annotated[str, Form(max_length=100)],
    image_width: Annotated[int, Form()],
    image_height: Annotated[int, Form()],
) -> dict:
    """Explicitly segment one declared Skill Model object in a still frame."""
    if Path(image.filename or "").suffix.lower() not in {".jpg", ".jpeg"} or image.content_type not in {"image/jpeg", "image/jpg"}:
        raise HTTPException(status_code=415, detail="Choose the JPEG snapshot from the camera check.")
    if not os.environ.get("MODEL_API_KEY") and not _repo_key_exists():
        raise HTTPException(status_code=503, detail="Set MODEL_API_KEY in the repository's local .env file first.")
    try:
        process = json.loads(process_json)
        if not isinstance(process, dict):
            raise ValueError("The reviewed process must be a JSON object.")
        validate_references(process)
        selected = next((item for item in process["objects"] if item["id"] == object_id), None)
        if selected is None:
            raise ValueError("Choose an object declared in the reviewed Skill Model.")
        with tempfile.TemporaryDirectory(prefix="showme-ground-") as temporary:
            image_path = Path(temporary) / "snapshot.jpg"
            size = _copy_bounded(image, image_path, max_bytes=MAX_SNAPSHOT_BYTES)
            if size == 0:
                raise ValueError("The camera snapshot is empty.")
            result = segment_image(
                MuseSparkClient.from_env().client,
                image_path,
                concept=selected["label"],
                width=image_width,
                height=image_height,
            )
            return result
    except (OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        image.file.close()


@app.post("/api/skills/inspect-joint")
def inspect_selected_joint(
    reference_image: Annotated[UploadFile, File(description="Explicitly selected source diagram/frame")],
    learner_image: Annotated[UploadFile, File(description="Explicitly selected learner frame")],
    process_json: Annotated[str, Form(max_length=100_000)],
    transition_id: Annotated[str, Form(max_length=100)],
    relationship_target: Annotated[str, Form(max_length=20)] = "all",
) -> dict:
    """Paid comparison only when explicitly requested; cannot establish recovery."""
    try:
        process = json.loads(process_json)
        if not isinstance(process, dict):
            raise ValueError("reviewed process must be a JSON object")
        validate_references(process)
        if transition_id not in {item["id"] for item in process["transitions"]}:
            raise ValueError("select a declared transition")
        with tempfile.TemporaryDirectory(prefix="showme-joint-") as temporary:
            paths = []
            for name, upload in [("reference", reference_image), ("learner", learner_image)]:
                suffix = Path(upload.filename or "").suffix.lower()
                if suffix not in {".jpg", ".jpeg", ".png"} or upload.content_type not in {"image/jpeg", "image/png"}:
                    raise HTTPException(status_code=415, detail="Select JPEG or PNG evidence images.")
                path = Path(temporary) / (name + suffix)
                if _copy_bounded(upload, path, max_bytes=MAX_SNAPSHOT_BYTES) == 0:
                    raise ValueError("evidence image is empty")
                paths.append(path)
            result = inspect_joint(MuseSparkClient.from_env(), paths[0], paths[1], process, transition_id, relationship_target=relationship_target)
            return {"inspection": result, "status": result["assessment"]}
    except (OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        reference_image.file.close()
        learner_image.file.close()


@app.post("/api/skills/reconcile-session")
def reconcile_physical_session(payload: dict) -> dict:
    """Local-only replay of explicit observations; no provider request or media upload."""
    try:
        process = payload.get("process")
        if not isinstance(process, dict):
            raise ValueError("provide a reviewed process object")
        return {"session": reconcile_session(process, payload.get("checks"))}
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/skills/compare-recovery")
def compare_joint_recovery(
    reference_image: Annotated[UploadFile, File()],
    before_image: Annotated[UploadFile, File()],
    after_image: Annotated[UploadFile, File()],
    process_json: Annotated[str, Form(max_length=100_000)],
    transition_id: Annotated[str, Form(max_length=100)],
    before_seconds: Annotated[float, Form()],
    after_seconds: Annotated[float, Form()],
) -> dict:
    """Explicit paid three-image comparison, not an automatic completion check."""
    try:
        process = json.loads(process_json)
        if not isinstance(process, dict):
            raise ValueError("provide a reviewed process object")
        validate_references(process)
        with tempfile.TemporaryDirectory(prefix="showme-recovery-") as temporary:
            paths = []
            for role, upload in [("reference", reference_image), ("before", before_image), ("after", after_image)]:
                suffix = Path(upload.filename or "").suffix.lower()
                if suffix not in {".jpg", ".jpeg", ".png"} or upload.content_type not in {"image/jpeg", "image/png"}:
                    raise HTTPException(status_code=415, detail="Select JPEG or PNG recovery evidence.")
                path = Path(temporary) / (role + suffix)
                if _copy_bounded(upload, path, max_bytes=MAX_SNAPSHOT_BYTES) == 0:
                    raise ValueError("recovery image is empty")
                paths.append(path)
            result = compare_recovery(MuseSparkClient.from_env(), *paths, process, transition_id, before_seconds, after_seconds)
            return {"comparison": result, "status": result["status"]}
    except (OSError, ValueError, RuntimeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    finally:
        for upload in [reference_image, before_image, after_image]:
            upload.file.close()


@app.post("/api/skills/guidance")
def source_linked_guidance(payload: dict) -> dict:
    """Local deterministic intervention guidance; no provider call."""
    try:
        process = payload.get("process")
        if not isinstance(process, dict):
            raise ValueError("provide a reviewed process object")
        return {"guidance": build_guidance(process, payload.get("report"), payload.get("report_kind"))}
    except (ValueError, TypeError, KeyError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def _copy_bounded(
    upload: UploadFile,
    destination: Path,
    *,
    max_bytes: int = MAX_UPLOAD_BYTES,
) -> int:
    total = 0
    with destination.open("wb") as output:
        while chunk := upload.file.read(1024 * 1024):
            total += len(chunk)
            if total > max_bytes:
                limit = "5 MB" if max_bytes == MAX_SNAPSHOT_BYTES else "100 MB"
                raise HTTPException(status_code=413, detail=f"Keep this upload under {limit}.")
            output.write(chunk)
    return total


def _validate_video(video: UploadFile) -> str:
    suffix = Path(video.filename or "").suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(status_code=415, detail="Choose an MP4, MOV, M4V, or WebM video.")
    return suffix


def _repo_key_exists() -> bool:
    env_file = Path(__file__).resolve().parents[2] / ".env"
    if not env_file.is_file():
        return False
    return any(line.strip().startswith("MODEL_API_KEY=") for line in env_file.read_text(encoding="utf-8").splitlines())
