# Numerical baseline development results

Simulation only. No Meta calls, hardware or novelty claim.

| World | Strategy | Completed | Median RMSE °C |
|---|---|---|---|
| coupled | fixed | 3/3 | 0.0188 |
| coupled | random | 3/3 | 0.0525 |
| coupled | disagreement | 3/3 | 0.0259 |
| delayed_sensor | fixed | 3/3 | 0.1755 |
| delayed_sensor | random | 3/3 | 0.4163 |
| delayed_sensor | disagreement | 3/3 | 0.1791 |

The disagreement method is a simple numerical heuristic, not yet a strong optimal-design baseline.
These development cases were used during implementation; they are not held-out evidence.
All methods use the same experiment count, duration and reset charge. Energy proxies can differ.
The displayed median includes completed runs only; completion counts expose failures.
Model selection uses whole-trial leave-one-out validation, with a fixed prior until two trials exist.
Challenge inputs are disclosed before prediction; outputs are revealed once, after the prediction file is committed.
