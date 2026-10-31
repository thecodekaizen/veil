# Matched five-action revision comparison

Eighteen fresh simulated systems; three new sealed schedules each. No Meta calls. All scores retained.

| Method | Median system mean RMSE °C | Systems with a failed schedule |
|---|---:|---:|
| frozen_initial | 0.0126 | 0/18 |
| batch_all_families_five_trials | 0.0080 | 0/18 |
| mismatch_revision_four_then_confirm | 0.0126 | 0/18 |

Revisions triggered: 6/18.
Confirmation rejection/abstention: 0/18.
Sealed failing systems without a confirmation warning: 0.

Five trials charge 600 simulated experiment seconds and 1500 reset seconds per method.
The batch baseline fits all five trials; the revision policy reserves trial five for independent confirmation.
The frozen reference observes the same trials but does not refit. All use both supplied families initially.
No advantage from Meta, hardware validation or calibrated uncertainty is established.
