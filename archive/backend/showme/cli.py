"""Command-line utilities for the SHOWME proof-of-magic experiment."""

from __future__ import annotations

import argparse
import hashlib
import time
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

from .media import extract_evidence_frames, make_model_video, prepare_video
from .meta import MuseSparkClient
from .evaluation import score_holoassist_observation
from .observe import observation_prompt, observe_video, validate_observation
from .process import validate_references
from .focus import inspection_prompt, inspection_schema, validate_inspection


def _default_output(video: Path, phase: str) -> Path:
    root = Path(__file__).resolve().parents[2]
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return root / ".showme-runs" / phase / f"{video.stem}-{stamp}"


def main() -> int:
    parser = argparse.ArgumentParser(prog="showme", description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)

    prepare = commands.add_parser(
        "prepare-video",
        help="inspect a local video and extract timestamped frame samples",
    )
    prepare.add_argument("video", type=Path, help="local source video; not uploaded")
    prepare.add_argument("--output", type=Path, help="new output directory")
    prepare.add_argument("--sample-every", type=float, default=1.0, help="requested interval in seconds")
    prepare.add_argument("--max-frames", type=int, default=24, help="maximum frame count (1–240)")

    evidence = commands.add_parser("inspect-frames", help="extract selected original-resolution evidence frames locally; no upload")
    evidence.add_argument("video", type=Path)
    evidence.add_argument("--times", type=float, nargs="+", required=True, help="seek timestamps in seconds")
    evidence.add_argument("--output", type=Path, help="new private output directory")

    learn = commands.add_parser(
        "learn-video",
        help="upload one MP4 to Muse Spark and save a candidate process model",
    )
    learn.add_argument("video", type=Path, help="local MP4 demonstration; uploaded for inference")
    learn.add_argument("--output", type=Path, help="new run directory")

    observe = commands.add_parser(
        "observe-video",
        help="compare a learner MP4 with a learned process and save evidence-linked observations",
    )
    observe.add_argument("process", type=Path, help="learned process JSON")
    observe.add_argument("video", type=Path, help="local learner MP4; uploaded for inference")
    observe.add_argument("--reference-pdf", type=Path, help="optional task instructions PDF; uploaded with learner clip")
    observe.add_argument("--output", type=Path, help="new run directory")

    joint = commands.add_parser("inspect-joint", help="compare explicitly selected source/learner images using Meta; paid request")
    joint.add_argument("process", type=Path)
    joint.add_argument("reference_image", type=Path)
    joint.add_argument("learner_image", type=Path)
    joint.add_argument("--transition", required=True)
    joint.add_argument("--relationship", choices=["all", "contact", "facing"], default="all")
    joint.add_argument("--output", type=Path)

    score = commands.add_parser(
        "score-holoassist",
        help="score local divergence timestamps against HoloAssist mistake annotations",
    )
    score.add_argument("annotation", type=Path, help="local HoloAssist annotation JSON; never sent to Muse")
    score.add_argument("observation", type=Path, help="SHOWME observation JSON")
    score.add_argument("--tolerance", type=float, default=0.0, help="extra interval margin in seconds (default: exact overlap)")

    args = parser.parse_args()
    if args.command == "score-holoassist":
        return _score_holoassist(args.annotation, args.observation, args.tolerance)
    if args.command == "inspect-joint":
        output = args.output or _default_output(args.learner_image, "joint-inspection")
        return _inspect_joint(args.process, args.reference_image, args.learner_image, args.transition, output, relationship_target=args.relationship)
    phase = {"learn-video": "learned", "observe-video": "observed"}.get(args.command, "prepared")
    output = args.output or _default_output(args.video, phase)
    if args.command == "inspect-frames":
        try:
            manifest = extract_evidence_frames(args.video, output, args.times)
        except (OSError, ValueError, RuntimeError) as exc:
            print(f"showme: {exc}", file=sys.stderr)
            return 2
        print(json.dumps({"directory": str(output.resolve()), "frames": len(manifest["frames"]), "uploaded": False}))
        return 0
    if args.command == "learn-video":
        return _learn_video(args.video, output)
    if args.command == "observe-video":
        return _observe_video(args.process, args.video, output, reference_pdf=args.reference_pdf)

    try:
        manifest = prepare_video(
            args.video,
            output,
            sample_every_seconds=args.sample_every,
            max_frames=args.max_frames,
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"showme: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({
        "prepared_directory": str(output.resolve()),
        "duration_seconds": manifest["source"]["duration_seconds"],
        "frames_written": len(manifest["frames"]),
        "audio_present": manifest["source"]["audio_present"],
        "source_sha256": manifest["source"]["source_sha256"],
    }, indent=2))
    return 0



def _learn_video(video: Path, output: Path) -> int:
    try:
        manifest = prepare_video(video, output / "media", sample_every_seconds=1, max_frames=24)
        model_video = make_model_video(video, output / "model-input.mp4")
        learner = MuseSparkClient.from_env()
        process = learner.learn(output / "model-input.mp4", duration_seconds=manifest["source"]["duration_seconds"])
        process["_run"]["source_media"] = manifest["source"]
        process["_run"]["model_media"] = model_video
        validate_references(process, duration_seconds=manifest["source"]["duration_seconds"])
        process["_validation"] = "passed"
        (output / "process.json").write_text(
            json.dumps(process, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"showme: {exc}", file=sys.stderr)
        return 2

    usage = process.get("_run", {}).get("usage", {})
    print(json.dumps({
        "run_directory": str(output.resolve()),
        "process_file": str((output / "process.json").resolve()),
        "model": process.get("_run", {}).get("model"),
        "states": len(process.get("states", [])),
        "transitions": len(process.get("transitions", [])),
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "validation": process.get("_validation", "not_run"),
    }, indent=2))
    return 0



def _observe_video(process_path: Path, video: Path, output: Path, *, reference_pdf: Path | None = None) -> int:
    try:
        process = json.loads(process_path.read_text(encoding="utf-8"))
        if not isinstance(process, dict):
            raise ValueError("learned process must be a JSON object")
        source_duration = process.get("_run", {}).get("source_media", {}).get("duration_seconds")
        validate_references(process, duration_seconds=source_duration)
        manifest = prepare_video(video, output / "media", sample_every_seconds=1, max_frames=24)
        model_video = make_model_video(video, output / "model-input.mp4")
        (output / "observe-prompt.txt").write_text(
            observation_prompt(process, manifest["source"]["duration_seconds"], has_reference=reference_pdf is not None),
            encoding="utf-8",
        )
        learner = MuseSparkClient.from_env()
        observation = observe_video(
            learner,
            output / "model-input.mp4",
            process,
            manifest["source"]["duration_seconds"],
            reference_pdf=reference_pdf,
        )
        # Preserve raw output even if structural validation rejects it. It is not a usable observation.
        (output / "observation-unvalidated.json").write_text(
            json.dumps(observation, ensure_ascii=False, indent=2) + "\n", encoding="utf-8",
        )
        validate_observation(observation, process, manifest["source"]["duration_seconds"])
        observation["_run"]["source_media"] = manifest["source"]
        observation["_run"]["model_media"] = model_video
        observation["_run"]["process_file"] = str(process_path.expanduser().resolve())
        (output / "observation.json").write_text(
            json.dumps(observation, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"showme: {exc}", file=sys.stderr)
        return 2

    print(json.dumps({
        "run_directory": str(output.resolve()),
        "observation_file": str((output / "observation.json").resolve()),
        "events": len(observation.get("events", [])),
        "divergences": len(observation.get("divergences", [])),
        "reference_checks": {
            status: sum(check.get("status") == status for check in observation.get("reference_checks", []))
            for status in ("matches_reference", "possible_mismatch", "not_shown", "unclear")
        },
        "recovery_status": observation.get("recovery_status"),
        "usage": observation.get("_run", {}).get("usage", {}),
    }, indent=2))
    return 0


def _score_holoassist(annotation_path: Path, observation_path: Path, tolerance: float) -> int:
    try:
        annotation = json.loads(annotation_path.read_text(encoding="utf-8"))
        observation = json.loads(observation_path.read_text(encoding="utf-8"))
        result = score_holoassist_observation(
            observation,
            annotation,
            tolerance_seconds=tolerance,
        )
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        print(f"showme: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


def _inspect_joint(process_path: Path, reference: Path, learner: Path, transition: str, output: Path, *, relationship_target: str = "all") -> int:
    """Preserve raw evidence and failures; never retry or overwrite an old run."""
    started = time.monotonic()
    created = False
    try:
        process = json.loads(process_path.read_text())
        validate_references(process)
        prompt = inspection_prompt(process, transition, relationship_target=relationship_target)
        inputs = []
        for role, path in [("reference", reference), ("learner", learner)]:
            if not path.is_file() or path.suffix.lower() not in {".jpg", ".jpeg", ".png"}:
                raise ValueError("select existing JPEG or PNG evidence")
            inputs.append({"role": role, "path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        output.mkdir(parents=True, exist_ok=False)
        created = True
        (output / "prompt.txt").write_text(prompt)
        (output / "process.json").write_text(json.dumps(process, indent=2))
        (output / "inputs.json").write_text(json.dumps(inputs, indent=2))
        result = MuseSparkClient.from_env().analyze_images([reference, learner], prompt=prompt,
            schema=inspection_schema(), schema_name="showme_joint_inspection")
        (output / "inspection-unvalidated.json").write_text(json.dumps(result, indent=2))
        validate_inspection(result, process, transition, relationship_target=relationship_target)
        from .focus import PROMPT_VERSION
        from .session import process_fingerprint
        result.setdefault("_run", {}).update({"prompt_version": PROMPT_VERSION, "transition_id": transition, "relationship_target": relationship_target,
            "process_sha256": process_fingerprint(process),
            "evidence_images": inputs, "elapsed_seconds": round(time.monotonic()-started, 2)})
        (output / "inspection.json").write_text(json.dumps(result, indent=2))
        print(json.dumps({"output": str(output), "assessment": result["assessment"], "seconds": result["_run"]["elapsed_seconds"]}))
        return 0
    except (OSError, ValueError, RuntimeError) as exc:
        if created:
            (output / "failure.json").write_text(json.dumps({"error": str(exc), "seconds": round(time.monotonic()-started, 2)}))
        print(f"showme: {exc}", file=sys.stderr)
        return 2
