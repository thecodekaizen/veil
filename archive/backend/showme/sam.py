"""Small, opt-in SAM 3.1 image grounding adapter for a reviewed Skill Model object."""

from __future__ import annotations

import asyncio
import base64
from pathlib import Path
from typing import Any, Iterable


def _async_events(events: Iterable[Any]):
    """Adapt the OpenAI SDK's synchronous event stream to Meta's async parser."""
    async def iterate():
        try:
            for event in events:
                yield event
        finally:
            close = getattr(events, "close", None)
            if close is not None:
                close()

    return iterate()


async def _parse_final_image(events: Iterable[Any]) -> Any:
    from meta_sam_parser import image_segmentation_format, parse_responses_stream

    parsed = parse_responses_stream(_async_events(events), image_segmentation_format())
    return await parsed.final_result()


def _serialize_result(result: Any, *, concept: str, width: int, height: int) -> dict[str, Any]:
    """Return only renderable geometry; never expose SAM's custom wire grammar."""
    from meta_sam_parser import decode_mask_to_svg_path

    detections: dict[str, dict[str, Any]] = {}
    for record in result.records:
        if record.kind == "box":
            detection = detections.setdefault(record.object_id, {"object_id": record.object_id})
            detection["box"] = {
                "left": record.left,
                "top": record.top,
                "right": record.right,
                "bottom": record.bottom,
            }
        elif record.kind == "mask":
            detection = detections.setdefault(record.object_id, {"object_id": record.object_id})
            detection["mask"] = {
                "width": record.mask.width,
                "height": record.mask.height,
                "bounds": {
                    "left": record.bounds.left,
                    "top": record.bounds.top,
                    "right": record.bounds.right,
                    "bottom": record.bounds.bottom,
                },
                "path": decode_mask_to_svg_path(record.mask),
            }

    if result.outcome.status != "completed":
        raise ValueError("SAM segmentation did not complete; no overlay was returned.")
    return {
        "model": "sam-3.1",
        "concept": concept,
        "image": {"width": width, "height": height},
        "detections": list(detections.values()),
        "diagnostics": [diagnostic.code for diagnostic in result.diagnostics],
    }


def segment_image(
    client: Any,
    image_path: Path,
    *,
    concept: str,
    width: int,
    height: int,
) -> dict[str, Any]:
    """Run one explicitly requested object segmentation on one still image."""
    concept = " ".join(concept.split())
    if not concept or len(concept) > 120:
        raise ValueError("Choose a short object name (up to 120 characters).")
    if not (1 <= width <= 1280 and 1 <= height <= 1280):
        raise ValueError("Snapshot dimensions must be between 1 and 1280 pixels.")

    try:
        import meta_sam_parser  # noqa: F401 - report a focused optional-dependency error below
    except ImportError as exc:
        raise RuntimeError("Install SAM support with: pip install -e '.[meta]'") from exc

    data_url = "data:image/jpeg;base64," + base64.b64encode(image_path.read_bytes()).decode("ascii")
    try:
        events = client.responses.create(
            model="sam-3.1",
            input=[{
                "type": "message",
                "role": "user",
                "content": [
                    {"type": "input_text", "text": concept},
                    {"type": "input_image", "image_url": data_url},
                ],
            }],
            stream=True,
            metadata={"mask_encoding": "one_bit"},
        )
        result = asyncio.run(_parse_final_image(events))
    except Exception as exc:
        # A segmentation call can be billable. Do not retry it automatically.
        raise RuntimeError(
            "Meta SAM request or mask parsing failed. Automatic retries are disabled; "
            "inspect billing before retrying."
        ) from exc
    return _serialize_result(result, concept=concept, width=width, height=height)
