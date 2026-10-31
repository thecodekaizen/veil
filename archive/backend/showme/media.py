"""Deterministic local video inspection and frame sampling for SHOWME experiments."""

from __future__ import annotations

from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
from typing import Any


def _run(args: list[str], *, timeout: int = 60) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(args, check=True, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Required program is not installed: {args[0]}") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(f"{args[0]} failed: {detail or 'no diagnostic output'}") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{args[0]} timed out after {timeout} seconds") from exc


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def inspect_video(path: Path) -> dict[str, Any]:
    """Read local video metadata without uploading or modifying the source."""
    source = path.expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"video file does not exist: {source}")

    result = _run([
        "ffprobe", "-v", "error", "-show_format", "-show_streams",
        "-of", "json", str(source),
    ])
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("ffprobe returned invalid JSON") from exc

    streams = payload.get("streams", [])
    video = next((item for item in streams if item.get("codec_type") == "video"), None)
    audio = next((item for item in streams if item.get("codec_type") == "audio"), None)
    if video is None:
        raise ValueError("input has no video stream")

    duration_value = video.get("duration") or payload.get("format", {}).get("duration")
    try:
        duration = float(duration_value)
    except (TypeError, ValueError) as exc:
        raise ValueError("could not read video duration") from exc
    if not math.isfinite(duration) or duration <= 0:
        raise ValueError("video duration must be finite and greater than zero")

    try:
        frame_rate = float(Fraction(video.get("avg_frame_rate", "0/1")))
    except (ValueError, ZeroDivisionError):
        frame_rate = None

    return {
        "source_name": source.name,
        "source_sha256": _sha256(source),
        "source_size_bytes": source.stat().st_size,
        "duration_seconds": duration,
        "width": int(video.get("width", 0)),
        "height": int(video.get("height", 0)),
        "video_codec": video.get("codec_name"),
        "average_frame_rate": frame_rate,
        "audio_present": audio is not None,
        "audio_codec": audio.get("codec_name") if audio else None,
        "container": payload.get("format", {}).get("format_name"),
        "inspected_at_utc": datetime.now(timezone.utc).isoformat(),
    }


def prepare_video(
    path: Path,
    output_dir: Path,
    *,
    sample_every_seconds: float = 1.0,
    max_frames: int = 24,
) -> dict[str, Any]:
    """Create a manifest and timestamp-named JPEG samples; leave source untouched."""
    if not math.isfinite(sample_every_seconds) or sample_every_seconds <= 0:
        raise ValueError("sample interval must be finite and greater than zero")
    if max_frames < 1 or max_frames > 240:
        raise ValueError("max_frames must be between 1 and 240")

    source = path.expanduser().resolve()
    metadata = inspect_video(source)
    output = output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=False)

    duration = metadata["duration_seconds"]
    interval = max(sample_every_seconds, duration / max_frames)
    times = []
    index = 0
    while index < max_frames:
        timestamp = index * interval
        if timestamp >= duration:
            break
        times.append(timestamp)
        index += 1
    if not times:
        times = [0.0]

    frames: list[dict[str, Any]] = []
    try:
        for frame_index, timestamp in enumerate(times):
            filename = f"frame-{frame_index:03d}-t{round(timestamp * 1000):08d}ms.jpg"
            destination = output / filename
            _run([
                "ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
                "-ss", f"{timestamp:.3f}", "-i", str(source),
                "-map", "0:v:0", "-frames:v", "1", "-q:v", "2", str(destination),
            ])
            if not destination.is_file() or destination.stat().st_size == 0:
                raise RuntimeError(f"ffmpeg produced no frame at requested time {timestamp:.3f}s")
            frames.append({
                "index": frame_index,
                "requested_time_seconds": round(timestamp, 3),
                "file": filename,
            })

        manifest = {
            "schema_version": 1,
            "preprocessing": "ffmpeg-seek-sample",
            "sample_interval_seconds": round(interval, 3),
            "source": metadata,
            "frames": frames,
        }
        (output / "manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        return manifest
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise


def make_model_video(source_path: Path, destination: Path) -> dict[str, Any]:
    """Make a bounded, silent MP4 for the P0 visual-only model pass."""
    source = source_path.expanduser().resolve()
    if not source.is_file():
        raise ValueError(f"video file does not exist: {source}")
    destination = destination.expanduser().resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    _run([
        "ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(source),
        "-map", "0:v:0", "-an", "-vf", "scale=1280:1280:force_original_aspect_ratio=decrease",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "24", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(destination),
    ])
    if not destination.is_file() or destination.stat().st_size == 0:
        raise RuntimeError("ffmpeg produced no model-input video")
    return {
        "filename": destination.name,
        "sha256": _sha256(destination),
        "size_bytes": destination.stat().st_size,
        "audio_removed": True,
        "max_dimension": 1280,
    }


def extract_evidence_frames(path: Path, output_dir: Path, timestamps: list[float]) -> dict[str, Any]:
    """Extract explicitly selected original-resolution frames locally, without labels or uploads.

    Timestamps are seek requests, not claims about the exact encoded frame time.
    Never overwrite an existing evidence packet.
    """
    if not timestamps or len(timestamps) > 60:
        raise ValueError("select between 1 and 60 evidence timestamps")
    if any(isinstance(t, bool) or not isinstance(t, (int, float)) or not math.isfinite(t) or t < 0 for t in timestamps):
        raise ValueError("evidence timestamps must be finite nonnegative numbers")
    source = path.expanduser().resolve()
    metadata = inspect_video(source)
    times = sorted(set(timestamps))
    if any(t >= metadata["duration_seconds"] for t in times):
        raise ValueError("evidence timestamps must be within the clip")
    output = output_dir.expanduser().resolve()
    output.mkdir(parents=True, exist_ok=False)
    frames = []
    try:
        for index, timestamp in enumerate(times):
            destination = output / f"frame-{index:03d}-t{round(timestamp * 1000):08d}ms.png"
            _run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{timestamp:.6f}",
                  "-i", str(source), "-map", "0:v:0", "-frames:v", "1", str(destination)])
            if not destination.is_file() or destination.stat().st_size == 0:
                raise RuntimeError(f"ffmpeg produced no evidence frame at {timestamp}s")
            frames.append({"requested_time_seconds": timestamp, "file": destination.name,
                           "sha256": _sha256(destination)})
        manifest = {"schema_version": 1, "purpose": "local-evidence-inspection",
                    "preprocessing": "ffmpeg-seek-original-resolution-png",
                    "timestamp_basis": "requested seek time; decoded frame presentation time not asserted",
                    "source": metadata, "frames": frames}
        (output / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return manifest
    except Exception:
        shutil.rmtree(output, ignore_errors=True)
        raise
