# Demo candidates (synthetic fixture only)
Both receipts are from `veil/artifacts/smoke-001/input.mp4` (synthetic, fictional values).
- `synth-before-track-start-fix/`: audit UNRESOLVED, OCR read the phone label at 0.0 s (SAM track started at frame 4).
- `synth-after-track-start-fix/`: after track-start extension + ±3-frame temporal padding the same finding is COVERED
  (extensions.json lists what each track received).
Development material, not gate results (gate NOT RUN).
