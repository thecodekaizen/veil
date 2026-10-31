# Real Meta controller integration

Live calls: 3. Estimated cost: $0.041374.
Generated simulated measurements, supplied model families, deliberately restricted initial no-lag model.
This is integration evidence, not a matched comparison or hardware result.

Charged experiments: 6/7. Independent confirmation supports: 0; rejections: 0.

| Action | RMSE °C | Verdict |
|---|---:|---|
| experiment-1 | 0.147530 | no_mismatch_observed |
| experiment-2 | 0.138449 | no_mismatch_observed |
| probe | 0.356402 | model_mismatch_observed |

Meta chose two legal diagnostics, then stopped without fitting alternatives. Passing other inputs did not resolve the initial mismatch.

Offline review recomputed predictions and scores, checked budget/event order, and verified confirmation inputs were absent from the candidate fitting evidence.
These checks establish internal consistency, not tamper-proof provenance. No automatic retries; each batch was separately capped at eight calls and $1.
