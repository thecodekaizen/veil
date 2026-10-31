from __future__ import annotations

import json

from meta_sam_parser import CompletedOutcome, ImageSegmentationResult, SegmentationBoxRecord
import pytest
from fastapi.testclient import TestClient

from showme.sam import _serialize_result, segment_image
from showme import api


PROCESS = {
    "task_summary": "Stack two blocks.",
    "objects": [
        {"id": "red", "label": "red block", "visual_description": "small red cube"},
        {"id": "blue", "label": "blue block", "visual_description": "large blue cube"},
    ],
    "states": [
        {"id": "separate", "description": "Blocks are separate", "observable_facts": ["gap between blocks"]},
        {"id": "stacked", "description": "Red is on blue", "observable_facts": ["red above blue"]},
    ],
    "transitions": [{
        "id": "stack", "from_state": "separate", "action": "stack red on blue", "object_ids": ["red", "blue"],
        "to_state": "stacked", "candidate_constraints": [], "postconditions": ["red above blue"],
        "evidence": [{"start_seconds": 0.2, "end_seconds": 0.8, "observation": "The red cube moves above the blue cube."}],
    }],
    "ordering_observations": [],
    "uncertainties": [],
}


def test_serialize_sam_boxes_into_image_geometry() -> None:
    result = ImageSegmentationResult(
        revision=1,
        records=(SegmentationBoxRecord(order=0, object_id="0", left=12, top=20, right=42, bottom=55),),
        diagnostics=(),
        raw_output="<parsed by official library>",
        outcome=CompletedOutcome(),
    )

    serialized = _serialize_result(result, concept="washer", width=320, height=240)

    assert serialized["model"] == "sam-3.1"
    assert serialized["image"] == {"width": 320, "height": 240}
    assert serialized["detections"] == [{
        "object_id": "0",
        "box": {"left": 12, "top": 20, "right": 42, "bottom": 55},
    }]


def test_empty_completed_sam_result_is_a_valid_no_match() -> None:
    result = ImageSegmentationResult(0, (), (), "", CompletedOutcome())

    serialized = _serialize_result(result, concept="washer", width=320, height=240)

    assert serialized["detections"] == []
    assert serialized["diagnostics"] == []


@pytest.mark.parametrize("concept,width,height", [("  ", 320, 240), ("washer", 0, 240), ("washer", 320, 1281)])
def test_invalid_grounding_request_is_rejected_before_api_call(concept: str, width: int, height: int) -> None:
    with pytest.raises(ValueError):
        segment_image(None, None, concept=concept, width=width, height=height)


def test_grounding_route_uses_only_a_declared_object_and_returns_overlay(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_repo_key_exists", lambda: True)
    monkeypatch.setattr(api.MuseSparkClient, "from_env", lambda: type("MetaClient", (), {"client": object()})())
    fake_result = {"model": "sam-3.1", "concept": "red block", "image": {"width": 20, "height": 10}, "detections": [], "diagnostics": []}
    segment = lambda *args, **kwargs: fake_result
    monkeypatch.setattr(api, "segment_image", segment)
    client = TestClient(api.app)

    response = client.post(
        "/api/skills/ground-object",
        files={"image": ("snapshot.jpg", b"jpeg", "image/jpeg")},
        data={"process_json": json.dumps(PROCESS), "object_id": "red", "image_width": 20, "image_height": 10},
    )

    assert response.status_code == 200
    assert response.json() == fake_result


def test_grounding_route_rejects_an_object_outside_the_skill_before_model_call(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api, "_repo_key_exists", lambda: True)
    called = False

    def should_not_segment(*args, **kwargs):
        nonlocal called
        called = True
        raise AssertionError("SAM must not run for an object outside the reviewed Skill Model")

    monkeypatch.setattr(api, "segment_image", should_not_segment)
    client = TestClient(api.app)
    response = client.post(
        "/api/skills/ground-object",
        files={"image": ("snapshot.jpg", b"jpeg", "image/jpeg")},
        data={"process_json": json.dumps(PROCESS), "object_id": "invented", "image_width": 20, "image_height": 10},
    )

    assert response.status_code == 422
    assert "declared in the reviewed Skill Model" in response.json()["detail"]
    assert not called
