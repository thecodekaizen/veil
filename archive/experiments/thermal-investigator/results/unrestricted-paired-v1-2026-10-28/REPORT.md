# Unrestricted paired comparison

Ten fresh simulated systems; identical seven-action ceilings and three supplied model families.
Shared initial selection uses BIC; no deliberately wrong initial model. All failures retained.

| Method | Median RMSE °C | Failed executions | Median actions used | Meta calls |
|---|---:|---:|---:|---:|
| fixed_bic | 0.004717 | 0/10 | 7.0 | 0 |
| disagreement_bic | 0.003032 | 0/10 | 7.0 | 0 |
| meta_direct | 0.008263 | 10/10 | 3.0 | 12 |
| meta_investigator | 0.008263 | 10/10 | 3.0 | 15 |

## Paired investigator minus baseline RMSE (negative favors investigator)

| Baseline | Median paired difference °C | Investigator wins / ties / losses |
|---|---:|---|
| fixed_bic | 0.002711 (95% bootstrap [0.000437, 0.004265]) | 1 / 0 / 9 |
| disagreement_bic | 0.003904 (95% bootstrap [0.001240, 0.007455]) | 1 / 0 / 9 |
| meta_direct | 0.000000 (95% bootstrap [0.000000, 0.000000]) | 0 / 10 / 0 |

Predeclared 20% median-error improvement gate versus both numerical baselines: FAIL.
Bootstrap intervals are descriptive with ten paired instances, not broad scientific proof.

Estimated total API cost: $0.275236. Not confirmed billing balance.
Early stopping uses fewer actual experiments; allowed ceilings are matched, realized actions need not be.
A lower-budget result is not an experiment-saving claim unless its accuracy target is met.
Ten instances and one pre-existing sealed schedule support feasibility only; no hardware or industrial claim.
