# Real Meta controller integration

Live calls: 7. Estimated cost: $0.101373.
Generated simulated measurements, supplied model families, deliberately restricted initial no-lag model.
This is integration evidence, not a matched comparison or hardware result.

Charged experiments: 6/7. Independent confirmation supports: 1; rejections: 1.

| Action | RMSE °C | Verdict |
|---|---:|---|
| experiment-3 | 0.388372 | revision_rejected |
| experiment-6 | 0.075339 | revision_supported_on_confirmation |
| probe | 0.304559 | model_mismatch_observed |

After clarifying provisional registration, Meta staged a quadratic-loss candidate, saw it rejected on both-release input, then fitted/staged sensor lag and obtained support on new staggered input. Both failed and supported revisions are retained.
The successful scenario follows policy amendments after earlier development failures; it is not an unbiased success-rate estimate. The task initially restricts the model family, so it cannot establish advantage over conventional full-family selection.

Offline review recomputed predictions and scores, checked budget/event order, and verified confirmation inputs were absent from the candidate fitting evidence.
These checks establish internal consistency, not tamper-proof provenance. No automatic retries; each batch was separately capped at eight calls and $1.
