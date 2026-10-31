"""One bounded development smoke pilot. Does not establish comparative superiority."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

from .meta import MetaDecider, load_api_key, PRICE_SOURCE
from .run import run_case, write_json


FROZEN = {
    "protocol": "meta-smoke-development-v0.1",
    "development_only": True,
    "seed": 11, "delayed": True,
    "additional_experiments": 2,
    "strategies": ["fixed", "random", "disagreement", "d_optimal", "meta_direct", "meta_investigator"],
    "primary_endpoint": "mean per-sensor held-out RMSE in degrees Celsius at matched action/time budget",
    "forecast_target_c": .3,
    "target_note": "Development feasibility target, 3.75x the declared observation noise standard deviation; not a hardware requirement.",
    "future_comparison_improvement_target_fraction": .2,
    "max_meta_calls": 6, "meta_budget_usd": 1.,
    "live_execution_status": "not_run_offline_milestone",
    "maximum_output_tokens_per_call": 2048,
    "price_source": PRICE_SOURCE,
    "limitations": ["one already-used development instance", "one fixed challenge input schedule",
                    "same supplied ARX families; no discovery of new physical equations",
                    "Meta policies differ in instructions; tools, raw evidence and numerical scores are equivalent",
                    "a smoke check cannot establish superiority, user value or a publishable result"],
}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--live", action="store_true", help="Permit at most the frozen six Meta calls within the local cost guard")
    args = parser.parse_args()
    if not args.live:
        print(json.dumps(FROZEN, indent=2))
        print("Dry run only. Add --live to execute this exact bounded pilot.")
        return
    args.output.mkdir(parents=True, exist_ok=False)
    frozen = {**FROZEN, "utc_frozen": datetime.now(timezone.utc).isoformat(),
              "source_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                                for p in sorted(Path(__file__).parent.glob("*.py"))}}
    write_json(args.output / "protocol-frozen-before-calls.json", frozen)
    provider = MetaDecider(load_api_key(args.env_file), args.output / "provider", max_calls=6, budget_usd=1.)
    results = []
    for strategy in FROZEN["strategies"]:
        result = run_case(args.output / strategy, 11, True, strategy, 2,
                          meta_decider=provider if strategy.startswith("meta_") else None)
        results.append(result)
        write_json(args.output / "partial-results.json", {"runs": results})
        print(json.dumps({"strategy": strategy, "rmse_c": result.get("mean_rmse_c"),
                          "status": result.get("status", "completed"),
                          "error": result.get("error"), "meta_calls": result.get("meta_calls", 0)}), flush=True)
    write_json(args.output / "results.json", {"protocol": frozen, "runs": results})
    lines = ["# Bounded Meta development smoke pilot", "", "Simulation only. One development instance. No superiority claim.", "",
             "| Strategy | Mean sensor RMSE °C | Calls | Status |", "|---|---:|---:|---|"]
    for r in results:
        error = f'{r["mean_rmse_c"]:.4f}' if "mean_rmse_c" in r else "—"
        lines.append(f'| {r["strategy"]} | {error} | {r.get("meta_calls", 0)} | {r.get("status", "completed")} |')
    lines += ["", "The two Meta conditions share numerical tools/results and raw observations; this first integration varies prompt policy.",
              "The model selects among supplied predictors and experiments. It has not generated a new physical model structure.",
              "Inspect provider/usage-state.json for all attempts, including failed or uncertain requests. No automatic retries.",
              "The full paired evaluation, physical-data check and scientific contribution gate remain outstanding."]
    (args.output / "REPORT.md").write_text("\n".join(lines) + "\n")
    print((args.output / "REPORT.md").read_text(), flush=True)
    if any(r.get("status") == "failed" for r in results):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
