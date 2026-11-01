# Open-weight discovery: Muse Glimmer 30B on a laptop (experimental, one clip)

Declared before results: every 3rd keyframe of gate clip c2 (9 frames), local `llama-server` (llama.cpp 0.8.0, unsloth UD-Q3_K_XL GGUF of Meta's Apache-2.0 weights, SHA-256 verified), Apple M4 Pro 24 GB. Same prompt and strict JSON schema as hosted Spark. SAM 3.1 (hosted) tracks the proposed concepts; the unchanged gate scorer scores c2. Keyframes never leave the laptop for this stage.

- Keyframes answered: **5/9** (4 hit the 600 s per-call timeout); median 559.0 s per keyframe; ~5.0 tokens/s generation (the 15 GB model swaps on 24 GB).
- Result: on c2: 2/2 planted leaks found, code-panel control not flagged

## Proposals (verbatim)

- frame 150: **personal name notification**: Shows name Rohan Kulkarni and parcel message, revealing identity
- frame 150: **surname overlay text**: Displays KULKARNI — 12, potentially identifying residence or building
- frame 225: **Message notification with name Rohan Kulkarni**: Displays personal name Rohan Kulkarni and parcel alert, linking identity to the filmed scene
- frame 225: **KULKARNI — 12 label**: Shows surname Kulkarni with number 12, suggesting residence or apartment identifier
- frame 375: **Personal name in message notification**: Shows 'Rohan Kulkarni' and 'Your parcel is at the gate', revealing a real name and a location-specific delivery alert
- frame 375: **Surname and house number on car window**: Displays 'KULKARNI — 12' on the vehicle, indicating family name and a residence identifier
- frame 450: **name overlay**: Displays 'KULKARNI — 12' which is a personal name/identifier that could link to creator or location
- Scorer output: `gate/glimmer/GATE_RESULT.md`. Its G1 'FAIL' is an artifact of scoring one clip (G1 expects all 4 leaks across c1-c3); G4 does not apply (c2 has no audio leak). Hosted Spark on the same clip (repeat r1, all 25 keyframes): 2/2 leaks, control flagged.

Caveats: one clip, a third of the keyframes, a 3-bit quantization, 4 timeouts. Hosted Spark saw all 25 keyframes. This shows the open-weight path works end to end; it is not a quality comparison.
