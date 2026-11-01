# GATE RESULT: FAIL

| criterion | result | evidence |
| --- | --- | --- |
| G1 discovery | PASS | 3/4 planted visual leaks matched by Spark concepts; 2 with in_baseline=false |
| G2 false flags | FAIL | 2/3 safe controls matched (limit 1) |
| G3 tracking | PASS | L4 100.0% (with held 100.0%); L2 100.0% (with held 100.0%); L3 100.0% (with held 100.0%) |
| G4a detection | PASS | A1: 5432210 exact=False edit=5 |
| G4b localization | FAIL | A1: coverage 79.2%, over-cover 0.49 s, method windowed/window_voiced, pad 0.5 s |
| G5 output re-check | UNRESOLVED listed | c1: face-output:45, face-output:50, face-output:60, face-output:365, face-output:425, face-output:460, face-output:465, face-output:480, face-output:485, face-output:490, face-output:505, face-output:510, face-output:525, face-output:530; c2: visual:baseline-license-plate, face-output:90 |

## G1 per leak
| clip | leak | concept | in_baseline | matched Spark concept | IoU | matched |
| --- | --- | --- | --- | --- | --- | --- |
| c1 | L1 | delivery box with an address label | True | None | 0.0 | False |
| c1 | L4 | society name board | False | green society sign | 0.982 | True |
| c2 | L2 | phone notification showing a name | True | message notification banner | 0.979 | True |
| c2 | L3 | door nameplate | False | name overlay text | 0.985 | True |

## G2 per control
| clip | control | best Spark concept | IoU | matched |
| --- | --- | --- | --- | --- |
| c1 | C1 | zenith logo sign | 0.79 | True |
| c2 | C2 | None | 0.0 | False |
| c3 | C3 | commercial buildings billboards | 0.989 | True |

## Interpretation notes
- G1/G2 IoU uses the SAM mask pixels (not its bbox) against the labelled ref_box; frames without a mask (held/padded) never count.
- A leak/control counts as matched if ANY of its ref_boxes is matched by a concept at that ref_box time (+/-2 frames).
- G1 aggregates visual leaks across all label files and expects exactly 4 planted visual leaks.
- G3 (gate decision) counts frames with a real SAM mask of ANY Spark concept that matches the leak (IoU>=0.5 at a ref_box) inside visible_ranges; coverage including held/padded frames is reported next to it.
- G4a takes the PII hit overlapping the labelled audio span (else the hit nearest to it); digit accuracy is reported, not gated.
- G5 is reported, not a kill criterion: PASS if the audit has no UNRESOLVED finding; otherwise the findings are listed.

**GATE.md: if G1-G4 fail, stop Veil; fallback = Andaaz gate at Sunday breakfast**
