"""Offline consistency review of a saved experiment; never calls a model or lab.

This verifies internal records, not the authenticity of the recorded measurements.
An attacker replacing the entire ledger and hashes is outside this check.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np


def review_run(directory: Path) -> dict:
    errors = []
    try:
        prediction_bytes = (directory / "prediction-commit.json").read_bytes()
        committed = json.loads(prediction_bytes)
        result = json.loads((directory / "result.json").read_text())
        events = [json.loads(line) for line in (directory / "events.jsonl").read_text().splitlines()]
        digest = hashlib.sha256(prediction_bytes).hexdigest()
        if result.get("prediction_sha256") != digest:
            errors.append("Prediction file does not match its recorded commitment")
        if [e["sequence"] for e in events] != list(range(len(events))):
            errors.append("Ledger sequence is missing, duplicated or reordered")
        commits = [i for i, e in enumerate(events) if e["kind"] == "prediction_committed"]
        reveals = [i for i, e in enumerate(events) if e["kind"] == "challenge_revealed"]
        if len(commits) != 1 or len(reveals) != 1 or commits[0] >= reveals[0]:
            errors.append("Expected exactly one prediction commitment before one challenge reveal")
        elif events[commits[0]]["payload"].get("sha256") != digest:
            errors.append("Ledger commitment differs from prediction file")
        if reveals and any(e["kind"] == "observation" for e in events[reveals[0]+1:]):
            errors.append("Training observations occurred after challenge disclosure")
        observations = [e["payload"] for e in events if e["kind"] == "observation"]
        ids = [o["observation_id"] for o in observations]
        if len(ids) != len(set(ids)):
            errors.append("Observation IDs must be distinct")
        if result.get("action_count") != len(observations):
            errors.append("Action count does not match the observations")
        time_cost = sum(o["experiment_s"] + o["reset_charge_s"] for o in observations)
        if not np.isclose(time_cost, result["experimental_time_s"]):
            errors.append("Recorded experimental time does not match its observations")
        predicted = np.asarray(committed["prediction"]["temperature_c"], dtype=float)
        actual = np.asarray(result["temperature_c"], dtype=float)
        if predicted.shape != actual.shape or predicted.ndim != 2 or predicted.shape[1] != 2:
            errors.append("Prediction and observation shapes differ")
        elif not np.isfinite(predicted).all() or not np.isfinite(actual).all():
            errors.append("Nonfinite prediction or challenge observation")
        else:
            per_sensor = np.sqrt(np.mean((predicted - actual) ** 2, axis=0))
            if not np.allclose(per_sensor, result["rmse_c_by_sensor"], atol=1e-10, rtol=1e-10):
                errors.append("Stored per-sensor scores do not match recomputed errors")
            if not np.isclose(per_sensor.mean(), result["mean_rmse_c"], atol=1e-10, rtol=1e-10):
                errors.append("Stored mean score does not match recomputed error")
        if reveals:
            disclosed = events[reveals[0]]["payload"]
            if disclosed["temperature_c"] != result["temperature_c"]:
                errors.append("Result challenge trace differs from the ledger reveal")
        return {"valid": not errors, "errors": errors,
                "strategy": result.get("strategy"), "observations": len(observations),
                "mean_rmse_c": result.get("mean_rmse_c"), "prediction_sha256": digest,
                "verification_scope": "saved-record internal consistency, not measurement authenticity",
                "model_calls_made_by_review": 0}
    except (OSError, ValueError, KeyError, TypeError, IndexError) as exc:
        return {"valid": False, "errors": ["Incomplete or invalid saved record: " + type(exc).__name__],
                "model_calls_made_by_review": 0}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    result = review_run(args.directory)
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["valid"] else 1)


if __name__ == "__main__":
    main()
