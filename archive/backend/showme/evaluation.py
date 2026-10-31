"""Local scoring helpers for SHOWME outputs against HoloAssist annotations."""

from __future__ import annotations

import math
from typing import Any


def score_holoassist_observation(
    observation: dict[str, Any],
    annotation: dict[str, Any],
    *,
    tolerance_seconds: float = 0.0,
) -> dict[str, Any]:
    """Score timestamped divergence predictions against annotated wrong actions.

    Each prediction can match at most one annotated interval, and each interval
    can be detected at most once. Labels are consumed locally; this function is
    intentionally separate from the model prompt and inference path.
    """
    if not math.isfinite(tolerance_seconds) or tolerance_seconds < 0:
        raise ValueError("tolerance_seconds must be finite and non-negative")
    if not isinstance(observation, dict) or not isinstance(annotation, dict):
        raise ValueError("observation and annotation must be JSON objects")

    duration = _number(
        annotation.get("video_duration", {}).get("seconds")
        if isinstance(annotation.get("video_duration"), dict)
        else None,
        "annotation video duration",
    )
    if duration <= 0:
        raise ValueError("annotation video duration must be positive")

    predicted = observation.get("divergences")
    if not isinstance(predicted, list):
        raise ValueError("observation divergences must be an array")
    predictions: list[float] = []
    for index, item in enumerate(predicted):
        if not isinstance(item, dict):
            raise ValueError(f"divergence {index} must be an object")
        timestamp = _number(item.get("time_seconds"), f"divergence {index} time_seconds")
        if not 0 <= timestamp < duration:
            raise ValueError(f"divergence {index} timestamp is outside the annotated clip")
        predictions.append(timestamp)

    targets = _holoassist_wrong_action_intervals(annotation, duration)
    candidates_by_prediction = [
        sorted(
            index for index, (start, end) in enumerate(targets)
            if start - tolerance_seconds <= timestamp <= end + tolerance_seconds
        )
        for timestamp in predictions
    ]
    target_to_prediction: dict[int, int] = {}

    def assign(prediction_index: int, visited_targets: set[int]) -> bool:
        for target_index in candidates_by_prediction[prediction_index]:
            if target_index in visited_targets:
                continue
            visited_targets.add(target_index)
            previous = target_to_prediction.get(target_index)
            if previous is None or assign(previous, visited_targets):
                target_to_prediction[target_index] = prediction_index
                return True
        return False

    for prediction_index in sorted(range(len(predictions)), key=lambda index: predictions[index]):
        assign(prediction_index, set())

    matched_prediction_indices = set(target_to_prediction.values())
    matches = [
        {
            "prediction_seconds": predictions[prediction_index],
            "label_start_seconds": targets[target_index][0],
            "label_end_seconds": targets[target_index][1],
        }
        for target_index, prediction_index in target_to_prediction.items()
    ]
    matches.sort(key=lambda item: item["prediction_seconds"])
    false_positives = [
        timestamp for index, timestamp in enumerate(predictions)
        if index not in matched_prediction_indices
    ]

    false_negatives = [
        {"start_seconds": targets[index][0], "end_seconds": targets[index][1]}
        for index in range(len(targets)) if index not in target_to_prediction
    ]
    true_positive = len(matches)
    precision = true_positive / len(predictions) if predictions else None
    recall = true_positive / len(targets) if targets else None
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall > 0
        else None
    )
    return {
        "clip": annotation.get("video_name"),
        "duration_seconds": duration,
        "tolerance_seconds": tolerance_seconds,
        "counts": {
            "true_positive": true_positive,
            "false_positive": len(false_positives),
            "false_negative": len(false_negatives),
            "predictions": len(predictions),
            "labeled_wrong_actions": len(targets),
        },
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "matches": matches,
        "false_positive_times_seconds": false_positives,
        "missed_label_intervals": false_negatives,
        "note": "Event-time scoring only; it does not score action identity, recovery quality, or annotation completeness.",
    }


def _holoassist_wrong_action_intervals(
    annotation: dict[str, Any], duration: float,
) -> list[tuple[float, float]]:
    actions = annotation.get("actions")
    if not isinstance(actions, list):
        raise ValueError("HoloAssist annotation actions must be an array")
    intervals: list[tuple[float, float]] = []
    for action_index, action in enumerate(actions):
        if not isinstance(action, dict):
            raise ValueError(f"action {action_index} must be an object")
        fine_actions = action.get("fine_grained_actions", [])
        if not isinstance(fine_actions, list):
            raise ValueError(f"action {action_index} fine_grained_actions must be an array")
        for fine_index, fine in enumerate(fine_actions):
            if not isinstance(fine, dict):
                raise ValueError(f"fine-grained action {action_index}:{fine_index} must be an object")
            attributes = fine.get("fine_grained_action_attributes")
            if not isinstance(attributes, dict):
                raise ValueError(f"fine-grained action {action_index}:{fine_index} is missing attributes")
            correctness = attributes.get("Action Correctness", "")
            if not isinstance(correctness, str) or not correctness.casefold().startswith("wrong action"):
                continue
            start = _number(fine.get("start_time"), f"label {action_index}:{fine_index} start_time")
            end = _number(fine.get("end_time"), f"label {action_index}:{fine_index} end_time")
            if not 0 <= start <= end <= duration:
                raise ValueError(f"label {action_index}:{fine_index} interval is outside the annotated clip")
            intervals.append((start, end))
    return sorted(intervals)


def _number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be a finite number")
    return float(value)
