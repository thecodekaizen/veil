# Evaluation

All numbers come from committed files. Footage: composited clips (licensed Wikimedia Commons footage + fictional graphics + macOS Hindi TTS, see `gate/exploratory/SOURCES.md`). This is **easier than real recordings** (flat sharp planted text, clean TTS). Not a privacy guarantee and not a general accuracy claim.

## 1. Frozen gate (pre-registered, `gate/GATE.md`, tag `gate-freeze`, commit `4ef8de9`): **FAIL**
Source: `gate/GATE_RESULT.md`, `gate/gate_result.json` (unchanged).

| Criterion | Result |
|---|---|
| G1 discovery | PASS (3/4 planted visual leaks; 2 not in the fixed baseline) |
| G2 false flags | **FAIL** (2/3 safe controls matched, limit 1) |
| G3 tracking | PASS (100% on covered leaks) |
| G4a spoken-number detection | PASS (digits not exact: edit distance 3) |
| G4b audio localization | **FAIL** (coverage 100%, over-cover 3.13 s, limit 2.5 s) |
| G5 output re-check | UNRESOLVED items listed (face detector hits in output sampled frames) |

GATE.md says to stop Veil if G1-G4 fail. Work continued by explicit decision (`SUBMISSION_DECISION.md`); the verdict above is not reinterpreted.

## 2. Value of Spark discovery (held-out c1-c3, `eval/results/final/heldout_results.md`)
Fixed baseline concepts (face, license plate, phone screen, paper document): **0/4** planted visual leaks matched. Baseline + Spark-proposed concepts: **3/4**. Missed: c1 L1 delivery-box label.

## 3. POST-GATE experiments (labelled; not the gate; `gate/postgate/`, run on the same held-out clips, so they are NOT an untouched evaluation)
Written after seeing the gate failure. Code: `veil/src/veil/stages/verify.py`, `listen.voiced_refine`. Thresholds in GATE.md unchanged; scorer unchanged.

| Fix | Targeted failure | Result |
|---|---|---|
| OCR mask-vs-claim verify | G2 C2: SAM grounded "name overlay label" on the code editor | Masklet rejected (OCR of the mask read `def total(items)`, not the claimed `KULKARNI`); the two real KULKARNI masklets verified. G2 now 1/3 (limit 1). |
| Not fixed | G2 C3: Spark itself proposed "commercial buildings billboards" matching the book cover | Remains matched. Inherent to open-vocabulary proposals. |
| Voiced-time PII span refinement | G4b over-cover | Two Voice runs of c3: over-cover 3.13 s then **2.85 s**, both still > 2.5 s. **G4b still FAIL.** Causes seen: Voice appended or misheard digit tokens ("...2100"), and ambient noise is counted as voiced. I did not tune the threshold on c3. |

Caveats: the verify check only applies to concepts that quote text (ALL-CAPS words / quoted strings); OCR can misread, so it may also wrongly reject a true leak (not observed in c1-c3, but 3 clips is not evidence). Voice output varies between runs; two runs are not a distribution. A post-gate "G2 PASS" must be read as: a narrow failure was fixed with a check designed after seeing it.

### 3b. POST-GATE experiment 2: lift the 10-concept Spark cap (`gate/postgate2/`, same clips, same caveat)
Owner asked to spend more; `VEIL_SPARK_CAP=50`, SAM re-tracked every proposed concept, plus verify and voiced refine. Cost of this run: 174 calls, est. $6.78.

| Criterion | Capped post-gate | Uncapped |
|---|---|---|
| G1 | PASS 3/4 | PASS 3/4 (L1 delivery-box label still missed) |
| G2 | PASS 1/3 | **FAIL 2/3**: new Spark concept "zenith logo sign" matched the product-logo control C1 |
| G4b | FAIL (coverage 100%, over-cover 2.85 s) | **FAIL (coverage 79.2%, over-cover 0.49 s)**: part of the spoken number was NOT muted |

Findings: more Spark concepts bring more false flags, not more leaks found. The voiced-time refinement can under-cover when Voice mis-times digits (1 of 3 Voice runs); under-coverage is the worse failure for privacy, so `--refine-voiced` stays opt-in and is not recommended. SAM stream errors left 3 c2 concepts NOT_CHECKED (shown, not hidden). The demo uses the capped post-gate runs.

### 3c. POST-GATE experiment 3: mask check also verifies cited proper names (`gate/repeats-v2/`, `eval/repeats-v2/`)
Three fresh end-to-end runs (uncapped, logged SAM retries, all checks). G1 4/4 in all three (12 of 12). G2 PASS in all three (0, 1, 1 of 3);
the c2 code-panel false flag no longer occurs. G4b FAIL in all three (3.13 s, 1.98 s with only 88% coverage, 3.13 s). NOT_CHECKED 4, 2, 2
(SAM stream errors left after retries). 769 calls, est. $22.06. Same clips, fix designed after seeing failures.

## 4. Dev set (synthetic fixture, `eval/results/final/dev_results.md`)
One synthetic clip, used for development and padding choice. Live re-run on 2026-11-01: all 8 visual findings COVERED, spoken number muted and re-transcription check ran, 0 faces in output samples.

## 5. Unit tests
`make test` -> 117 passed (no network).

## Not measured
Real phone recordings, real Hinglish speech, cost per clip (ledger estimate ~$0.1 per 18 s run, not reconciled to billing), precision/recall beyond the above, open-weight model.
