# Bounded Meta development smoke pilot

Simulation only. One development instance. No superiority claim.

| Strategy | Mean sensor RMSE °C | Calls | Status |
|---|---:|---:|---|
| fixed | 0.1946 | 0 | completed |
| random | 0.4135 | 0 | completed |
| disagreement | 0.8469 | 0 | completed |
| d_optimal | 0.3692 | 0 | completed |
| meta_direct | 0.3692 | 3 | completed |
| meta_investigator | 0.3692 | 3 | completed |

The two Meta conditions share numerical tools/results and raw observations; this first integration varies prompt policy.
The model selects among supplied predictors and experiments. It has not generated a new physical model structure.
Inspect provider/usage-state.json for all attempts, including failed or uncertain requests. No automatic retries.
The full paired evaluation, physical-data check and scientific contribution gate remain outstanding.
