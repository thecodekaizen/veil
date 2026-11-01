# GATE RESULT: FAIL

| criterion | result | evidence |
| --- | --- | --- |
| G1 discovery | FAIL | 2/2 planted visual leaks matched by Spark concepts; 1 with in_baseline=false |
| G2 false flags | PASS | 0/1 safe controls matched (limit 1) |
| G3 tracking | PASS | L2 100.0% (with held 100.0%); L3 100.0% (with held 100.0%) |
| G4a detection | FAIL |  |
| G4b localization | FAIL |  |
| G5 output re-check | UNRESOLVED listed | c2: visual:baseline-license-plate |

## G1 per leak
| clip | leak | concept | in_baseline | matched Spark concept | IoU | matched |
| --- | --- | --- | --- | --- | --- | --- |
| c2 | L2 | phone notification showing a name | True | message notification banner | 0.979 | True |
| c2 | L3 | door nameplate | False | message notification banner | 0.993 | True |

## G2 per control
| clip | control | best Spark concept | IoU | matched |
| --- | --- | --- | --- | --- |
| c2 | C2 | None | 0.0 | False |

## Interpretation notes
- G1/G2 IoU uses the SAM mask pixels (not its bbox) against the labelled ref_box; frames without a mask (held/padded) never count.
- A leak/control counts as matched if ANY of its ref_boxes is matched by a concept at that ref_box time (+/-2 frames).
- G1 aggregates visual leaks across all label files and expects exactly 4 planted visual leaks.
- G3 (gate decision) counts frames with a real SAM mask of ANY Spark concept that matches the leak (IoU>=0.5 at a ref_box) inside visible_ranges; coverage including held/padded frames is reported next to it.
- G4a takes the PII hit overlapping the labelled audio span (else the hit nearest to it); digit accuracy is reported, not gated.
- G5 is reported, not a kill criterion: PASS if the audit has no UNRESOLVED finding; otherwise the findings are listed.

**GATE.md: if G1-G4 fail, stop Veil; fallback = Andaaz gate at Sunday breakfast**
