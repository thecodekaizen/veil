# Natural editing: milestone-one implementation checkpoint

Date: 28 October 2026. This extends VEIL; no historical THREAD/SHOWME or reference frontend files changed.

## Baseline before modifications

- HEAD `49f5f75`; branch main. Existing uncommitted historical `apps/web/` and `docs/handoff/IMPLEMENTATION.md` changes preserved.
- Existing renderer: per-frame cover and face-only blur, FFmpeg H.264/AAC; existing Timeline remains unchanged.
- Baseline test run in actual product directory: 30 passed, 3 skipped (compiled local OCR cache absent); same result outside sandbox before cache creation.
- Consulted LIVE_EVALUATION.md, DATASET_EVALUATION.md and actual model schemas/renderer/OCR. Existing controlled successes do not establish new replacement accuracy.

## Minimal extension

`media.redact.render(..., natural_replacements=[SurfaceReplacement(...)])` is optional. Existing callers and default behavior remain compatible.

Each plan names an existing cover-protected plate/phone track and a persistent asset. Every protected frame either gets a valid supplied quad or retains the existing opaque cover. Missing asset, missing quad, invalid perspective, occluded/uncertain status lead to recorded fallback. No new probability or model-confidence score is invented.

`media.surface`: validates clockwise cyclic TL/TR/BR/BL corners, convexity, minimum size, source boundaries and protective support; warps one texture via homography; fully overwrites interior; blends only an exterior one-pixel rim; uses a clipped scalar illumination gain. It does not reconstruct shadows, reflections or foreground hands. Other mandatory redactions are applied afterward.

`media.surface_tracking`: optional one-source-frame initialization, pyramidal LK forward/backward filtering and RANSAC homography; stops after tracking loss, requires explicit reinitialization. Inlier fraction is a geometric diagnostic, not confidence. No automatic initial localization, complete-occlusion recovery or re-entry is claimed.

`verification.original_text`: reuses native OCR on independently decoded exported frames, checks normalized original identifiers and contiguous four-character fragments, and binds report to exact MP4 hash. It does not trust edit decisions or approve arbitrary generated identifiers. Missing OCR is incomplete review; clean OCR still requires visual review. The ordinary verifier is unchanged and may still flag a fictional plate as a plate; policy-aware live integration remains pending.

## Real local outputs: natural-surface-001

Purely generated six-second 640×360, 12 fps clip (72 frames). Fictional vehicle-like context, fake plate `2025550146`, mild perspective and background motion. This is a development fixture, not natural-camera evidence or an independent benchmark.

- `original.mp4`: planted number. Independent OCR recovered complete value in 72/72 frames.
- `opaque.mp4`: existing renderer, same target regions; original value/fragments not observed in all-frame OCR (separate audit addendum).
- `natural.mp4`: supplied per-frame fixture corners; persistent `DEMO` texture; 72 replacement frames, no fallback; no original value/four-digit fragment observed by all-frame OCR.
- `fallback.mp4`: geometry deliberately omitted for frames 24–25; 70 natural frames and exactly two opaque fallbacks; no original value/fragments observed by all-frame OCR.
- `tracked/natural-tracked.mp4`: only first quad initializes LK/RANSAC; 72 natural frames, no fallback. Mean corner error 0.7223 px, maximum frame-mean error 1.2720 px against withheld fixture corners evaluated after rendering. No original value/fragments observed by 72-frame exported OCR.
- All four initial outputs decode 72 frames with audio, video duration 6.000 s; encoded containers 6.016 s vs source 6.000 s. Audio is silence in this fixture, so intelligible-speech preservation is untested.
- No near-full-frame blackouts in the decoded outputs.
- Supplied-geometry natural edit changes about 9.86% of image pixels before encoding. Mean absolute source/output difference outside a 16-pixel neighborhood of the surface is 2.52/255, including codec recompression. This is not a perceptual quality score.
- First local render/audit batch elapsed 10.64 s; tracked follow-up about 3.06 s on this machine. Zero model API calls; $0 additional API cost.

Reviewed the original/opaque/natural contact sheet and all 72 supplied-geometry and all 72 LK-tracked output plate crops. The same `DEMO` content remains visible across the sequence; no original digits visible on these review sheets. This is assistant frame inspection, not an independent human panel or blinded preference result. No arbitrary-video beauty claim.

## Evidence and reproducibility

`artifacts/natural-surface-001/`: MP4s, asset, timeline, surface plan, render/fallback decisions, hashes, all-frame OCR observations, audit reports, quality report, contact and full-sequence review sheets. Intermediate decoded PNGs and silent render files need not be committed. Earlier results are preserved; opaque audit is recorded as an addendum.

```
PYTHONPATH=src python scripts/run_surface_demo.py --root artifacts/natural-surface-NEW --ocr-cache artifacts/private/ocr-cache
PYTHONPATH=src python scripts/run_surface_tracking.py --root artifacts/natural-surface-NEW
```

Requires FFmpeg/OpenCV and macOS Vision for the independent local OCR. Scripts refuse to overwrite prior experiment directories. No model credentials required.

Final regression run: **50 passed**, including native OCR checks after cache compilation, real renderer timing/fallback, geometry failures and local optical-flow tests. No model-backed tests were run.

## Status and next gate

- VERIFIED: opt-in renderer, persistent texture, explicit fallback, playable MP4, native exported-pixel OCR on one synthetic fixture, local tracking from one initial quad.
- UNTESTED: automatic model-driven corner localization; phone-screen/document datasets; occluder-preserving composition; glare/reflections/motion-blur matching; six independent cases; blinded visual preference; API/SDK natural-mode request and revision-bound policy-aware general audit.
- Fixture protective boxes are still supplied for every frame, including the tracked follow-up. This is not fully automatic protection.
- Next implementation: evaluate corner estimates inside independently detected protective regions, add tracking-loss/occlusion cases and known-original audit handling, then run the fixed six-case pilot before exposing natural mode in the API. Preserve opaque fallback; do not weaken the 4/6 and privacy gates.
