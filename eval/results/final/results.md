# Eval: baseline-only vs baseline+Spark (synthetic clip, development check)

| target | frames | baseline-only mean cover | baseline+Spark mean cover | baseline-only frames >=90% | baseline+Spark frames >=90% |
| --- | --- | --- | --- | --- | --- |
| face_source_panel | 180 | 0.39 | 0.39 | 0.0% | 0.0% |
| plate | 180 | 0.97 | 0.97 | 93.3% | 93.3% |
| printed_phone | 180 | 0.00 | 0.98 | 0.0% | 97.8% |

Audio: spoken span 4.9-9.371s, muted [(4.0, 10.0)], span covered 100.0%, over-cover 1.53 s, detected digits ['2025550146'] (true 2025550146), window precision.

## Caveats
- One synthetic clip; targets are rendered panels, not real footage. This is a development check, not the preregistered gate (gate NOT RUN).
- face_source_panel is the whole rendered portrait panel; the models cover the face inside it, so ~0.39 cover is a ground-truth-definition effect, not a measured miss of the face.
- The concept set was developed while looking at this clip; numbers are not held-out evidence.
