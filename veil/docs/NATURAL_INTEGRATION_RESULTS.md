# Natural editing: integration results and remaining gate

28 October 2026. Local native checks plus one explicit two-call Meta exported-media review. These are repeated development scenes, not six independent cases.

## Implemented

- Opt-in `POST /natural`, `GET /natural-review`, SDK `process_natural`, `protect_natural` and review retrieval.
- Reuse detected/reviewed protective Timeline, automatic local contour candidates or one manual source quad, persistent fixed fictional assets, LK/RANSAC, per-frame replacement/fallback.
- Source OCR positive controls; actual exported MP4 all-frame original-value/fragment checks; one targeted opaque re-render when a residual survives; export withholding on unavailable/incomplete checks or unexpected blackouts.
- Per-track strategy, template hash, fallback frames/reasons, separate visual diagnostics, exact output hash/revision. Changed exports invalidate review; broad residual findings block natural export. Existing repair invalidates natural evidence; a fresh reviewed job is currently required for a new natural clearance.
- Existing generic renderer/API behavior remains unchanged. No public asset paths/per-frame replacement quads accepted in the new request.

## Actual SDK/HTTP runs

| Evidence directory | Condition | Observed result |
| --- | --- | --- |
| `natural-api-001` | automatic contour, original 72-frame development clip | 72 natural frames; no original fragments observed; downloaded hash matches audit |
| `natural-api-wrong-001` | initial quad deliberately shifted; protective boxes enlarged | candidate residuals on 15 checked frames, then affected track entirely covered; new output has no original fragments observed |
| `natural-api-occlusion-001` | derived clip with generated full occlusion, frames 24–35 | 24 natural frames then 48 opaque fallback frames; original visible again after occlusion stays protected but natural tracking does not recover |
| `natural-api-002` | repeat normal run after final receipt fields | 72 natural frames; explicit final strategy/asset hash; original fragments absent in all-frame OCR |
| `natural-meta-replay-001` | old 180-frame synthetic clip with saved real Meta geometry | 168 natural plate frames, 12 support-boundary fallbacks; no tested original plate value/fragments observed |
| `natural-meta-blur-replay-001` | same saved geometry, existing opt-in face blur | same 168/12 plate result; all 180 printed-phone regions stay covered; known spoken-number interval max amplitude and RMS both zero |

All runs decode complete expected frames, preserve video duration (container AAC padding differs), and show zero near-full-frame blackouts. Initial 72-frame run timings roughly 6.4 s normal, 8.5 s wrong geometry, 5.9 s occlusion. The saved-Meta replays took roughly 25 s and 31.4 s including source and output native OCR. Machine-specific observations, not latency promises.

Saved-Meta runs reuse SAM/Spark protective plate/face tracks, actual Voice intervals and saved output-audit/OpenCV phone geometry from `live-pipeline-003`. They use no fresh detection calls and are labeled client-supplied replay timelines. One current-frame contour initializes the new plate plane; fixture truth is not used for tracking. Separate AFTER-render evaluation loads the old synthetic labels to check printed-phone and audio preservation.

Face blur is an optional inherited operation, not proof of face de-identification. Printed phone remains opaque in this comparison. Occluded plate frames visibly fall back to covers, not seamless reconstruction.

## Fresh Meta output audit

`natural-meta-audit-001`: existing broad verifier inspected the exact `natural-api-002` exported bytes. Two actual calls: Spark three exported frames and Voice exported audio; local OCR inspected 25 output frames at 250 ms maximum cadence. All checks completed; `no_exposure_observed_in_samples`. Estimated cost $0.0029225, not reconciled billing. No retries. Transfers and raw responses are retained.

This broad sampled check is separate from the 72-frame native original-text check. It does not make general verification continuous or establish external accuracy. No model calls occur in deterministic unit tests.

## Visual inspection and evidence

`natural-meta-blur-replay-001/comparison.mp4` and `.jpg`: source / existing face-blur + opaque plate / natural plate + face blur. Representative frames at 2, 7.6 and 16 s show plate replacement and the explicit opaque occlusion fallback. Assistant visual inspection is not a blinded human preference panel. Preserved rejection and fallback videos remain in the wrong-geometry run.

Core receipts separately retain quality `review_required`: outside-protected-region differences, blackouts, frame counts, tracking diagnostics and limitations. They do NOT turn low differences into a beauty score. Local alignment/homography validity cannot certify privacy; a seeded wrong-location example demonstrates that failure.

## Current acceptance

- VERIFIED: local natural API/SDK/export loop; targeted original-identifier inspection, automatic local contour initialization on development fixture, actual wrong-geometry rejection/fallback, safe loss behavior, reuse of real Meta geometry/audio, separate fresh broad Meta review.
- FAILED as a natural-editing condition: full-occlusion example loses tracking and uses covers for the rest of the clip. It is not counted as visually successful natural editing.
- UNTESTED: fixed six-case real/consented pilot, natural-scene generalization, glare/reflection handling, occluder-preserving reconstruction, document/screen footage and blinded user preference.
- MISSING: user explicitly chose to proceed without a new self-recorded screen clip. Do not repeatedly ask for it or substitute generated video as if it were that case.
- DEFERRED optional features: room-tone editing and generative removal. Existing conservative audio mute remains.

**Natural-editing benchmark gate: INSUFFICIENT EVIDENCE, not passed.** Existing redaction/verification/repair baseline remains independently available. Finish actual source selection and visual evaluation with Antigravity; do not turn these diagnostic variants into six independent successes.
