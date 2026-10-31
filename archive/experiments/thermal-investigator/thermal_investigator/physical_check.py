"""Local check of supplied physical model families; no model API calls."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import numpy as np
import scipy

from .contracts import experiment_library, initial_schedule
from .physical import physical_candidates
from .run import LabClient, write_json


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    source_hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                     for p in sorted(Path(__file__).parent.glob('*.py'))}
    write_json(args.output/"development-config.json", {
        "development_only": True, "seed": 11, "experiment_schedules": ["initial-common", "left-pulse", "right-pulse"],
        "supplied_model_families": ["two_node_thermal", "two_node_thermal_with_sensor_lag"],
        "source_sha256": source_hashes, "scipy_version": scipy.__version__, "meta_calls": 0})
    results = []
    for delayed in (False, True):
        directory = args.output / ("development-delayed" if delayed else "development-coupled")
        directory.mkdir()
        client = LabClient(11, delayed, 3)
        try:
            observations = [client.request({"operation": "experiment", "schedule": p.to_dict()})
                            for p in [initial_schedule()]+experiment_library()[:2]]
            write_json(directory/"public-observations.json", {"observations": observations})
            candidates = physical_candidates(observations)
            # Selection uses only whole-trial validation, before the challenge outputs.
            chosen = min(candidates, key=lambda m: m.validation_rmse_c)
            inputs = client.request({"operation": "challenge_inputs"})
            prediction = {"temperature_c": chosen.predict(inputs["commands_fraction"], inputs["ambient_c"]).tolist()}
            committed = {"utc": datetime.now(timezone.utc).isoformat(), "models": [m.to_dict() for m in candidates],
                         "selected_spec": chosen.spec.to_dict(), "challenge_inputs": inputs, "prediction": prediction}
            write_json(directory/"prediction-commit.json", committed)
            digest = hashlib.sha256((directory/"prediction-commit.json").read_bytes()).hexdigest()
            result = client.request({"operation": "challenge", "prediction": prediction})
            if hashlib.sha256((directory/"prediction-commit.json").read_bytes()).hexdigest() != digest:
                raise RuntimeError("Prediction changed after challenge")
            result.update({"development_only": True, "supplied_family": True,
                           "selected_spec": chosen.spec.to_dict(), "prediction_sha256": digest,
                           "source_sha256": source_hashes,
                           "scipy_version": scipy.__version__, "meta_calls": 0})
            write_json(directory/"result.json", result)
            results.append(result)
            print(json.dumps({"system": directory.name, "rmse_c": result["mean_rmse_c"],
                              "sensor_lag_selected": chosen.spec.sensor_lag,
                              "sensitivity_rank": chosen.sensitivity_rank,
                              "parameter_count": len(chosen.rates)}), flush=True)
        finally:
            client.close()
    lines = ["# Physical-model calibration development check", "",
             "Simulation only. Supplied physical families, fitted numerically. No Meta calls.", "",
             "| Development system | Selected sensor lag | Mean sensor RMSE °C |", "|---|---|---:|"]
    for label, result in zip(["coupled", "sensor delay"], results):
        lines.append(f'| {label} | {result["selected_spec"]["sensor_lag"]} | {result["mean_rmse_c"]:.5f} |')
    lines += ["", "Selection uses whole-trial validation, before challenge measurements are revealed.",
              "Only two already-used development instances and one challenge schedule were checked.",
              "Physical model families, parameter bounds and equations were supplied by the developer.",
              "This is calibration within a bounded family, not discovery of arbitrary laws or proven real-world mechanisms.",
              "The separately coded exact matrix-exponential predictor is checked against the RK4 environment.",
              "No hardware, industrial savings, held-out superiority or substantive Meta contribution is established."]
    (args.output/"REPORT.md").write_text("\n".join(lines)+"\n")
    write_json(args.output/"results.json", {"runs": results,
        "limitations": ["two known development instances", "supplied physical families", "simulation only",
                        "no Meta decisions", "no arbitrary equation discovery", "one challenge input schedule"]})


if __name__ == "__main__":
    main()
