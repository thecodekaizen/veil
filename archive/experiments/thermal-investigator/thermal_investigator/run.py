from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import uuid

import numpy as np

from .contracts import DT, experiment_library, initial_schedule
from .predictor import choose_disagreement, fit_candidates, select_model
from .design import choose_d_optimal
from .decisions import public_context


class LabClient:
    def __init__(self, seed: int, delayed: bool, max_actions: int):
        command = [sys.executable, "-m", "thermal_investigator.lab", "--seed", str(seed),
                   "--max-actions", str(max_actions)]
        if delayed:
            command.append("--delayed")
        self.process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                        text=True, bufsize=1)

    def request(self, payload: dict) -> dict:
        if self.process.stdin is None or self.process.stdout is None:
            raise RuntimeError("Lab pipe unavailable")
        self.process.stdin.write(json.dumps(payload, allow_nan=False) + "\n")
        self.process.stdin.flush()
        line = self.process.stdout.readline()
        if not line:
            raise RuntimeError("Lab process terminated")
        result = json.loads(line)
        if not result["ok"]:
            raise ValueError(result["error"])
        return result["result"]

    def close(self):
        if self.process.stdin:
            self.process.stdin.close()
        try:
            self.process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.process.kill()
            self.process.wait()
        if self.process.stdout:
            self.process.stdout.close()


def write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def run_case(output: Path, seed: int, delayed: bool, strategy: str, additional: int, meta_decider=None) -> dict:
    output.mkdir(parents=True, exist_ok=False)
    ledger = output / "events.jsonl"

    def event(kind, payload):
        entry = {"sequence": len(ledger.read_text().splitlines()) if ledger.exists() else 0,
                 "utc": datetime.now(timezone.utc).isoformat(), "kind": kind, "payload": payload}
        with ledger.open("a") as stream:
            stream.write(json.dumps(entry, allow_nan=False) + "\n")

    lab = LabClient(seed, delayed, additional + 1)
    observations, selections, decisions, meta_usage = [], [], [], []
    plans = experiment_library()
    rng = np.random.default_rng(seed + 100000)
    start = time.monotonic()
    try:
        initial = initial_schedule()
        first = lab.request({"operation": "experiment", "schedule": initial.to_dict()})
        observations.append(first)
        event("observation", first)
        for step in range(additional):
            candidates = fit_candidates(observations)
            if strategy in ("meta_direct", "meta_investigator"):
                if meta_decider is None:
                    raise ValueError("Meta strategy requires an explicitly configured provider")
                context = public_context(observations, candidates, plans, decisions=decisions)
                event("public_decision_context", context)
                decision, usage = meta_decider.decide(context, strategy)
                decisions.append(decision)
                meta_usage.append(usage)
                plan = next(p for p in plans if p.id == decision["schedule_id"])
                reason = {"selector": strategy, "decision": decision, "usage": usage}
            elif strategy == "fixed":
                plan = plans[0]
                reason = {"selector": "predeclared_library_order"}
            elif strategy == "random":
                plan = plans[int(rng.integers(len(plans)))]
                reason = {"selector": "uniform_without_replacement"}
            elif strategy == "d_optimal":
                plan, reason = choose_d_optimal(candidates, observations, plans)
            elif strategy == "disagreement":
                plan, reason = choose_disagreement(candidates, plans)
            else:
                raise ValueError("Unknown experiment strategy")
            event("proposal", {"schedule": plan.to_dict(), "reason": reason,
                               "candidate_models": [m.to_dict() for m in candidates]})
            observed = lab.request({"operation": "experiment", "schedule": plan.to_dict()})
            observations.append(observed)
            selections.append(plan.id)
            plans.remove(plan)
            event("observation", observed)
        candidates = fit_candidates(observations)
        model = select_model(candidates)
        if strategy in ("meta_direct", "meta_investigator"):
            context = public_context(observations, candidates, [], decisions=decisions, final=True)
            event("public_decision_context", context)
            decision, usage = meta_decider.decide(context, strategy)
            decisions.append(decision)
            meta_usage.append(usage)
            model = next(m for m in candidates if m.order == decision["model_order"])
            event("final_model_decision", {"decision": decision, "usage": usage})
        inputs = lab.request({"operation": "challenge_inputs"})
        prediction = {"temperature_c": model.predict(inputs["commands_fraction"], inputs["ambient_c"]).tolist()}
        committed = {"model": model.to_dict(), "challenge_inputs": inputs, "prediction": prediction}
        write_json(output / "prediction-commit.json", committed)
        commitment = hashlib.sha256((output / "prediction-commit.json").read_bytes()).hexdigest()
        event("prediction_committed", {"sha256": commitment})
        result = lab.request({"operation": "challenge", "prediction": prediction})
        event("challenge_revealed", result)
        # Verify that the scored prediction is the file actually committed before disclosure.
        if hashlib.sha256((output / "prediction-commit.json").read_bytes()).hexdigest() != commitment:
            raise RuntimeError("Prediction commitment changed after reveal")
        result.update({"strategy": strategy, "selected_schedules": selections,
                       "model_order": model.order, "action_count": len(observations),
                       "experimental_time_s": sum(o["experiment_s"] + o["reset_charge_s"] for o in observations),
                       "energy_proxy_fraction_seconds": sum(o["command_energy_proxy_fraction_seconds"] for o in observations),
                       "wall_seconds": time.monotonic() - start, "prediction_sha256": commitment,
                       "meta_calls": sum(not u["cache_hit"] for u in meta_usage),
                       "meta_cache_hits": sum(u["cache_hit"] for u in meta_usage),
                       "meta_estimated_usd": sum(u["estimated_usd"] for u in meta_usage if not u["cache_hit"]),
                       "model_decisions": decisions})
        write_json(output / "result.json", result)
        return result
    except Exception as exc:
        failure = {"strategy": strategy, "error": str(exc), "status": "failed",
                   "wall_seconds": time.monotonic() - start,
                   "meta_calls_before_failure": sum(not u["cache_hit"] for u in meta_usage)}
        write_json(output / "result.json", failure)
        return failure
    finally:
        lab.close()


def plot_svg(output: Path, case_dir: Path) -> None:
    committed = json.loads((case_dir / "prediction-commit.json").read_text())
    result = json.loads((case_dir / "result.json").read_text())
    measured = np.asarray(result["temperature_c"])
    predicted = np.asarray(committed["prediction"]["temperature_c"])
    all_values = np.vstack([measured, predicted])
    lower = float(all_values.min()) - 1
    upper = float(all_values.max()) + 1
    def points(values):
        return " ".join(f"{70 + i * 760/(len(values)-1):.2f},{330-(v-lower)*250/(upper-lower):.2f}"
                        for i, v in enumerate(values))
    lines = ['<svg xmlns="http://www.w3.org/2000/svg" width="940" height="430" viewBox="0 0 940 430">',
             '<rect width="940" height="430" fill="white"/>',
             '<g font-family="sans-serif" fill="#172126">',
             '<text x="40" y="30" font-size="18">Development simulation — unseen schedule</text>',
             '<text x="40" y="54" font-size="13">Solid: hidden simulator sensor trace · Dashed: committed numerical prediction · No Meta calls</text>',
             f'<text x="40" y="395" font-size="13">{result["strategy"]} · mean sensor RMSE {result["mean_rmse_c"]:.3f} °C · one development case, not comparative proof</text>',
             '<text x="410" y="365" font-size="13">Time (seconds)</text>']
    for j in range(6):
        value = lower + j * (upper - lower) / 5
        y = 330 - j * 50
        lines.append(f'<line x1="70" x2="830" y1="{y}" y2="{y}" stroke="#ddd"/>')
        lines.append(f'<text x="18" y="{y+4}" font-size="12">{value:.1f}°C</text>')
    for seconds in (0, 30, 60, 90, 120):
        lines.append(f'<text x="{70+seconds*760/120-5}" y="348" font-size="12">{seconds}</text>')
    for sensor, color in enumerate(("#2457b2", "#bc4d20")):
        lines.append(f'<polyline points="{points(measured[:,sensor])}" fill="none" stroke="{color}" stroke-width="2"/>')
        lines.append(f'<polyline points="{points(predicted[:,sensor])}" fill="none" stroke="{color}" stroke-width="2" stroke-dasharray="7 5"/>')
        lines.append(f'<text x="845" y="{100+sensor*24}" font-size="13" fill="{color}">Sensor {sensor+1}</text>')
    lines.append('</g></svg>')
    output.write_text("\n".join(lines))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(".runs") / str(uuid.uuid4()))
    parser.add_argument("--seeds", type=int, nargs="+", default=[11, 23, 37])
    parser.add_argument("--additional", type=int, default=3)
    parser.add_argument("--strategies", nargs="+", choices=["fixed", "random", "disagreement", "d_optimal"],
                        default=["fixed", "random", "disagreement", "d_optimal"])
    args = parser.parse_args()
    if not 1 <= args.additional <= 6 or any(seed < 0 for seed in args.seeds) or len(set(args.seeds)) != len(args.seeds):
        parser.error("Use 1–6 additional experiments and unique nonnegative seeds")
    args.output.mkdir(parents=True, exist_ok=False)
    config = {"protocol": "development-v0.2", "development_only": True,
              "additional_experiments": args.additional, "seeds": args.seeds,
              "sample_interval_s": DT, "strategies": args.strategies,
              "worlds": ["coupled", "delayed_sensor"], "meta_calls": 0, "python_version": sys.version, "numpy_version": np.__version__,
              "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted(Path(__file__).parent.glob("*.py"))},
              "limitations": ["one predeclared challenge schedule", "three development seeds by default",
                              "idealized exact ambient reset with 300 second charge", "ARX predictors are not physical mechanism discoveries",
                              "no held-out pilot and no hardware validation"]}
    write_json(args.output / "development-config.json", config)
    results = []
    case_names = []
    for delayed in (False, True):
        for seed in args.seeds:
            for strategy in config["strategies"]:
                case_name = f"dev-{'lag' if delayed else 'coupled'}-{seed}-{strategy}"
                result = run_case(args.output / case_name, seed, delayed, strategy, args.additional)
                result["development_world"] = "delayed_sensor" if delayed else "coupled"
                result["seed"] = seed
                results.append(result)
                case_names.append(case_name)
    write_json(args.output / "development-results.json", {"config": config, "runs": results})
    rows = ["# Numerical baseline development results", "", "Simulation only. No Meta calls, hardware or novelty claim.", "",
            "| World | Strategy | Completed | Median RMSE °C |", "|---|---|---|---|"]
    for world in config["worlds"]:
        for strategy in config["strategies"]:
            subset = [r for r in results if r["development_world"] == world and r["strategy"] == strategy]
            errors = [r["mean_rmse_c"] for r in subset if "mean_rmse_c" in r]
            median = f"{np.median(errors):.4f}" if errors else "failed"
            rows.append(f"| {world} | {strategy} | {len(errors)}/{len(subset)} | {median} |")
    rows += ["", "Disagreement is a simple heuristic. D-optimal design uses regularized ARX regressor information, an approximation under measurement noise.",
             "These development cases were used during implementation; they are not held-out evidence.",
             "All methods use the same experiment count, duration and reset charge. Energy proxies can differ.",
             "The displayed median includes completed runs only; completion counts expose failures.",
             "Model selection uses whole-trial leave-one-out validation, with a fixed prior until two trials exist.",
             "Challenge inputs are disclosed before prediction; outputs are revealed once, after the prediction file is committed."]
    (args.output / "REPORT.md").write_text("\n".join(rows) + "\n")
    success = next((case for case, r in zip(case_names, results) if "mean_rmse_c" in r), None)
    if success:
        plot_svg(args.output / "development-prediction.svg", args.output / success)
    print((args.output / "REPORT.md").read_text())
    print("Saved artifacts:", args.output.resolve())
    if any(r.get("status") == "failed" for r in results):
        sys.exit(1)


if __name__ == "__main__":
    main()
