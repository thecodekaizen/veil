# Thermal Investigator — numerical experiment

This is the first implementation of the experimental-investigator plan. It learns temperature-response predictors from bounded experiments and independently scores a future input schedule. **Current status: numerical baselines, one completed bounded Meta smoke check, and physical-model calibration development checks. No demonstrated Meta advantage or hardware validation.**

## Run

Requires Python 3.12+ and NumPy 1.26+:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e .
.venv/bin/python -m thermal_investigator.run --output .runs/my-development-run
.venv/bin/python -m unittest discover -s tests -v
```

Each output directory must be new. `--additional 3` chooses three additional experiments after the common initial trace. `--seeds 11 23 37` selects development instances; those cases are not held out. The lab runs in a separate local process. There is no provider/network call.

The Codex bundled Python runtime also has NumPy available; it was used for the recorded development run. Its absolute path is machine-specific and is not required for ordinary installation.

## What runs

- Original two-node lumped thermal simulation with optional sensor lag, noisy readings, bounded heater commands and fixed-duration experiments.
- Numerical autoregressive predictors of orders one and two, fitted by regularized least squares.
- Whole-trial leave-one-out validation for model selection. If a reduced-data fit is unstable but the full-data model is valid, its validation remains explicitly incomplete.
- Fixed schedules, random schedules, a simple between-family disagreement selector and regularized D-optimal regressor design.
- Prediction commitment before challenge results, SHA-256 integrity check, JSON event ledger, error report and SVG trace plot.

This code is not copied from TCLab, and it is not validated against TCLab hardware. Standard heat-balance equations supply the simulator; predictor coefficients do not establish the true mechanism. Candidate models receive observed traces and controls, not hidden coefficients or labels.

## Experimental assumptions

Every trial starts from idealized exact ambient equilibrium. A standardized 300-second reset charge is accounted for; no physical cooling procedure has been verified. Heater commands are limited to 65%, every experiment lasts 120 seconds, and sampling is every two seconds. The simulator enforces a 60°C temperature ceiling; this is not hardware safety certification.

Observed training readings contain 0.08°C Gaussian noise. Evaluation scores against the hidden noise-free sensor trace, explicitly labeled in the result. The 10°C normalization is a fixed development reference scale; absolute RMSE is the interpretable headline metric.

One public challenge input schedule is used here. The output remains sealed until the model's prediction file is written, after which the investigation closes. These are development examples, not the planned randomized held-out evaluation.

All strategies have the same action count, duration and reset charge. Energy proxies vary and are reported; this is a time-budget comparison, not a matched-energy experiment. Numerical disagreement is a heuristic and is not the strongest conventional optimal-design baseline promised in the final protocol.

## Isolation limits

The process boundary prevents accidental imports of hidden state into the predictor. It is not an operating-system sandbox. Future Meta tools must expose only the public lab interface and cannot receive shell/filesystem access, private configuration or challenge output files. The comparison runner knows the development seed; the eventual agent must not.

## Development result

The 18-case run across two systems, three development seeds and three strategies completed after correcting validation handling. Fixed schedules had the lowest median error on both systems. The simple active heuristic has not shown an advantage. No superiority or novelty claim follows from this run.

See `results/development-2026-10-28/REPORT.md` when present in the repository. Full local runs live under ignored `.runs/`.

## Next implementation

1. Implement a stronger conventional active-design baseline and freeze evaluation thresholds/cases.
2. Add evidence-linked Meta decisions through a bounded declarative specification.
3. Compare that investigator and a direct tool-using Meta agent with equal information, models and budgets.
4. Build the product workspace once the scientific decision gate passes.


## Offline inspection and Meta integration

```sh
python -m thermal_investigator.review results/development-doptimal-2026-10-28/dev-lag-11-d_optimal
python -m thermal_investigator.pilot --output .runs/unused-dry-run
```

The first command recomputes scores and checks commitments, ledger order and budgets from saved files. It makes no lab/model calls and verifies internal consistency, not the authenticity of the observations. The second command only displays the frozen development pilot. It does not read an API key or create a run directory.

The `--live` pilot path is explicit and bounded to six decision calls and a $1 local guard. Its first completed development check used six calls at an estimated $0.0463. Credit preservation is a current priority; no paid experiment or automatic retry is started by normal local runs. Prices were verified against https://dev.meta.ai/docs/pricing-rate-limits on 28 October 2026. Guards reserve estimated cost before a request and retain uncertain attempts. Provider billing remains authoritative.

Both Meta policies receive the same measured traces, numerical candidates and experiment scores. They choose among supplied ARX families and legal schedules; this is not generation of new physical equations. Explanations must cite available observations and unsupported choices fail validation. A single development instance is a smoke check only.

The latest numerical run has 24 completed cases, across four methods and the same three development seeds. D-optimal design improves median coupled-system error from 0.0188°C to 0.0162°C, but has worse delayed-sensor error than the fixed method (0.2438°C versus 0.1755°C). This approximation assumes regressor information without whitening input-output measurement noise; it is not guaranteed optimal physical experimental design. No overall advantage has been established.


## Physical-model calibration

Install the optional scientific dependency before running the physical-model check:

```sh
python -m pip install -e '.[science]'
python -m thermal_investigator.physical_check --output .runs/my-physical-development-check
python -m unittest discover -s tests -v
```

`physical.py` compiles a bounded two-node heat-flow model, optionally with sensor response lag. Positive effective loss/coupling rates and heater gains are fitted with constrained numerical least squares. Exact discrete transitions use SciPy's matrix exponential. Specifications and estimated coefficients can be exported and executed without model calls or arbitrary generated code.

The two supplied model families are compared using whole-trial validation. Effective rates do not individually identify thermal capacities, heat-transfer conductances or heater wattage. The numerical sensitivity-rank diagnostic is local and does not prove physical identifiability.

On two development instances with the fixed initial/left/right experiments, the matching supplied family was selected and the mean sensor prediction errors were 0.01240°C and 0.01234°C. These are simulation development results, not broad validation. All 30 checks pass with the science extra installed; the physical-specific suite is skipped if SciPy is absent.

The earlier Meta smoke check selected exactly the D-optimal schedules in both policies and achieved the same 0.3692°C error. Fixed ARX experiments were better (0.1946°C). Those results have not been replaced with the later physical-model result: model families and methods differ, and the Meta improvement gate remains unmet.
