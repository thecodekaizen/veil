# Persistent investigation walkthrough

One noiseless simulated sensor-delay system, seed 601, with three imported initial trials charged to the five-action session budget. This is a deterministic integration walkthrough, not a blind evaluation or Meta result.

1. Fit the supplied model without sensor delay from the initial public observations.
2. Freeze its sustained-heating prediction and reserve action four before dispatch.
3. Measure 0.40953°C diagnostic error; record the mismatch.
4. Register a supplied sensor-delay model fitted to the four observed trials, citing the mismatch and preserving the original model.
5. Freeze a prediction on a different confirmation schedule, reserve action five, close the database and reopen it.
6. Complete confirmation after restart. Error is approximately 4.8e-10°C because the noiseless simulator is within the supplied fitted family. This is not realistic instrument accuracy.
7. Repeat the completed confirmation request: the saved result is returned without execution or another charge.

All five action slots are charged. The revision policy was written by the developer. No Meta calls occurred. No claim of autonomous structure discovery, superiority, hardware control or global reliability is supported by this example.

A dispatched action whose outcome is unknown cannot run again automatically. An operator/executor must reconcile it with an observation. This preserves conservative budget accounting and avoids blind retries; exactly-once external hardware execution is not guaranteed by SQLite.
