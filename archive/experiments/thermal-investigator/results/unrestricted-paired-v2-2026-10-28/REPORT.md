# Unrestricted paired comparison

Ten fresh simulated systems; identical seven-action ceilings and three supplied model families.
Shared initial selection uses BIC; no deliberately wrong initial model. All failures retained.

| Method | Median RMSE °C | Failed executions | Median actions used | Meta calls |
|---|---:|---:|---:|---:|
| fixed_bic | 0.005194 | 0/10 | 7.0 | 0 |
| disagreement_bic | 0.006903 | 0/10 | 7.0 | 0 |
| meta_direct | 0.006682 | 0/10 | 5.5 | 78 |
| meta_investigator | 0.006682 | 0/10 | 7.0 | 68 |

## Paired investigator minus baseline RMSE (negative favors investigator)

| Baseline | Median paired difference °C | Investigator wins / ties / losses |
|---|---:|---|
| fixed_bic | 0.001254 (95% bootstrap [-0.001433, 0.006544]) | 3 / 0 / 7 |
| disagreement_bic | 0.000236 (95% bootstrap [-0.001584, 0.003933]) | 5 / 0 / 5 |
| meta_direct | 0.000000 (95% bootstrap [0.000000, 0.000000]) | 0 / 10 / 0 |

Predeclared 20% median-error improvement gate versus both numerical baselines: FAIL.
Bootstrap intervals are descriptive with ten paired instances, not broad scientific proof.

Estimated total API cost: $2.152036. Not confirmed billing balance.
Early stopping uses fewer actual experiments; allowed ceilings are matched, realized actions need not be.
A lower-budget result is not an experiment-saving claim unless its accuracy target is met.
Ten instances and one pre-existing sealed schedule support feasibility only; no hardware or industrial claim.
