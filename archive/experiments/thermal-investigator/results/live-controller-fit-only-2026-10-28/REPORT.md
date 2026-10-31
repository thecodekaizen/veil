# Real Meta controller integration

Live calls: 8. Estimated cost: $0.138739.
Generated simulated measurements, supplied model families, deliberately restricted initial no-lag model.
This is integration evidence, not a matched comparison or hardware result.

Charged experiments: 7/7. Independent confirmation supports: 0; rejections: 0.

| Action | RMSE °C | Verdict |
|---|---:|---|
| experiment-3 | 0.567096 | model_mismatch_observed |
| experiment-4 | 0.447941 | model_mismatch_observed |
| experiment-5 | 0.447152 | model_mismatch_observed |
| probe | 0.440034 | model_mismatch_observed |

Meta fitted alternatives, but kept testing the original model and exhausted its experiment budget without staging a candidate. The interface wording made provisional registration look like premature acceptance.

Offline review recomputed predictions and scores, checked budget/event order, and verified confirmation inputs were absent from the candidate fitting evidence.
These checks establish internal consistency, not tamper-proof provenance. No automatic retries; each batch was separately capped at eight calls and $1.
