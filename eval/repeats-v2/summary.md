# End-to-end repeats (post-gate, NOT the frozen gate)

Each repeat re-ran every stage on c1-c3 (fresh Spark discovery, SAM 3.1 tracking with up to 2 logged retries, Voice), concept cap 50, verify stage on, frozen bleep method. Same clips as the gate, so this measures run-to-run variance, not generalization.

| repeat | G1 discovery | G2 false flags | G3 tracking | G4a digits | G4b mute window | G5 output re-check | NOT_CHECKED findings | verdict |
|---|---|---|---|---|---|---|---|---|
| r1 | PASS 4/4 | PASS 0/3 | PASS | PASS | FAIL 3.13 s over | UNRESOLVED listed | 4 | FAIL |
| r2 | PASS 4/4 | PASS 1/3 | PASS | PASS | FAIL 1.98 s over | UNRESOLVED listed | 2 | FAIL |
| r3 | PASS 4/4 | PASS 1/3 | PASS | PASS | FAIL 3.13 s over | UNRESOLVED listed | 2 | FAIL |

## Model calls (all repeats)

| model | calls | failed | median latency s | p90 latency s | est. USD |
|---|---|---|---|---|---|
| muse-spark-1.3 | 225 | 0 | 3.54 | 4.54 | 0.61 |
| muse-voice-transcribe-1.0 | 306 | 0 | 1.82 | 2.47 | 0.03 |
| sam-3.1 | 238 | 40 | 19.44 | 314.29 | 21.41 |

Clip runs: 9; est. USD per clip run: mean 2.45 (min 0.56, max 4.05); total 22.06. Estimates from the call ledgers, not reconciled to billing.
