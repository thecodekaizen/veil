# Eval (HELD-OUT set): baseline-only vs baseline+Spark

| clip | leak | in_baseline | baseline-only (IoU / frames with mask) | baseline+Spark (IoU / frames with mask) |
| --- | --- | --- | --- | --- |
| c1 | L1 delivery box with an address label | True | no 0.0 / 0.0% | no 0.0 / 0.0% |
| c1 | L4 society name board | False | no 0.0 / 0.0% | matched 0.968 / 100.0% |
| c2 | L2 phone notification showing a name | True | no 0.0 / 0.0% | matched 0.979 / 100.0% |
| c2 | L3 door nameplate | False | no 0.0 / 0.0% | matched 0.983 / 100.0% |

Matched visual leaks: baseline-only 0/4, baseline+Spark 3/4.
Audio c3/A1: detected=4987651543210 exact=False edit=3, coverage 100.0%, over-cover 3.13 s (windowed); baseline has no audio component.
