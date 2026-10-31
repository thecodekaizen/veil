# Implementation progress

## Phase 1: capability smoke test

- [x] Generate 18-second wholly synthetic video, movement, partial occlusion, fake plate, printed/spoken fake number.
- [x] Real SAM image and video requests; decoded temporal masks and explicit frame geometry.
- [x] Real Voice request and turn timestamps; record incorrect digits as failure.
- [x] Real Spark contextual localization.
- [x] Render playable visual/audio-redacted MP4.
- [x] Inspect exported pixels/audio without original findings or answer key in prompts.
- [x] Detect deliberately omitted printed number.
- [x] Preserve failed single-digit repair; verifier rejects it.
- [x] Repair whole observed field with optical flow; re-render and inspect three frames.
- [x] Inspect 180 decoded frames and muted audio; save receipt, costs and limitations.

Result: viable constrained smoke slice, **not full P0**. SAM concept plate detection failed. Voice exact digits failed. Source was composited, not a real-camera clip. Final model review sampled three frames. No broad recall claims.

## Next vertical slice

- [x] Refactor real inference into a bounded pipeline with persistent local jobs; broad policy configuration remains pending.
- [ ] Add complete output sampling/OCR and an independent detector; distinguish seeded misses from natural misses.
- [ ] Evaluate additional synthetic clips, exposures, occlusions and negative controls; precision/recall and residual rate with sample sizes.
- [ ] Add atomic job/call bookkeeping, timeout/error handling, general audio/video validation and timestamp preservation beyond this fixed-FPS fixture.
- [x] Expose real create/reviewed-timeline-render/download HTTP path and thin Python SDK; tested against live loopback server.
- [x] Wire real detection, sampled output verification and targeted repair into job routes; live 8-call evaluation saved.
- [ ] Only then build reference interface and submission demo.

Invariant: verifier reads exported media; it must never accept protector metadata or evaluation labels as evidence that content is safe. Same-family model review can share failure modes. Record uncertain intervals and require human review.

## API slice evidence

Eight tests pass. `artifacts/api-roundtrip.json` records the real SDK → HTTP → engine → downloaded 180-frame MP4 roundtrip. This replay uses saved real-inference geometry, not fresh model inference. Receipts explicitly say automatic detection and privacy verification were not run. No additional model charges. Atomic manifests and per-job lock files prevent simultaneous mutation; interrupted-process recovery remains manual.


## Live core integration

Real Meta pipeline now runs through the HTTP API and SDK. Seventeen tests pass, including local OCR positive/negative checks, cloud-consent gating, revision invalidation and multi-fragment repair. Read PIPELINE_API.md and LIVE_EVALUATION.md for the current contract and preserved failures.

Latest output: 180 decoded frames; visible plate/digit region coverage 1.0 throughout the controlled fixture; known speech interval silent; no near-full-frame blackouts; three-frame model/OCR audit found no exposure. Eight real requests, estimated $0.09069. Earlier coordinate errors and degraded masking are preserved, not counted as successes.

Next: additional synthetic scenes and short-exposure/negative controls, configurable policies, denser independent inspection and stronger multiple-object association. No general recall/precision benchmark or real-camera validation yet.


## Additional-scene verification tests

- [x] Commit fixed three-scene protocol and fixtures before live inference (`67edcb3`).
- [x] Six bounded real Meta requests, with answer keys excluded and input hashes verified.
- [x] Preserve sparse baseline's missed 250 ms phone exposure.
- [x] Denser local OCR detects that exposure without new model calls; one clean control remains unflagged.
- [x] Integrate bounded 250 ms OCR, multi-signal fusion, incomplete-review status and revision-bound receipt coverage.
- [x] 25 tests pass in the build environment, including actual short-exposure and negative-control OCR checks.

See VERIFIER_BENCHMARK.md for counts, cost, latency, reproduction and limitations. These are verifier-only comparisons on three composited clips; shorter/misaligned exposures, long benign identifiers, multiple moving objects and presence-aware short-lived-object repair remain open.


## Optional face blur

- [x] Explicit face-only blur in validated timeline, detect API and SDK; opaque default preserved.
- [x] Mandatory opaque text/plate covers, including overlap and pixel-spread safeguards.
- [x] Freshly render and audit optional face-blur variant with two real Meta requests (estimated $0.004672).
- [x] Full 180-frame fixture-region/audio checks remain intact; 29 local tests pass in build environment.

See REDACTION_STYLES.md. Geometry remains padded boxes; no contour-mask or anonymity guarantee is claimed.


## Public-camera hybrid and presence-bounded fields

Removed 2026-11-01: the Pexels stock-footage hybrid test (fetch/protocol/results docs, scripts and `public-footage-001` artifacts) was withdrawn because the footage's license and consent chain was not verified from a primary source. Its claims (42/42 phone frames, 12 requests, estimated $0.0558) are no longer supported by files in the repository; the code changes it motivated (observation association, gap splitting, bounded envelopes) remain covered by the unit tests.

## Natural replacement extension — 28 October checkpoint

- [x] Opt-in persistent planar texture, validated homography, local contour initialization and LK/RANSAC tracking.
- [x] Explicit per-frame opaque fallback on uncertain/missing/out-of-support geometry; prior renderer unchanged by default.
- [x] Independent all-frame exported-text audit with source positive controls, exact file hashes, one affected-track fallback, incomplete-review blocking.
- [x] Existing HTTP jobs/API and thin SDK support natural mode; untrusted asset paths are not accepted.
- [x] Actual SDK/HTTP normal, bad-seed, occlusion and saved-real-Meta-geometry runs; preservation of phone/audio protections checked after rendering.
- [x] One fresh broad Meta audit: two actual requests, estimated $0.0029225, no exposure observed in sampled checks.
- [x] Per-track strategy receipts and separate utility diagnostics; stale/current review distinctions and export guards.
- [ ] Fixed six-case real/consented benchmark: not complete. Self-recorded screen case is missing by user instruction; dataset shortlist requires factual corrections.
- [ ] Independent blinded visual preference: not run. Do not count agent review as votes.
- [ ] Natural editing accepted for submission: NOT established by development success.

Read NATURAL_API.md, NATURAL_INTEGRATION_RESULTS.md, and the root ANTIGRAVITY_REVIEW_FEEDBACK.md. Naturalness, broad privacy, and targeted original-text checks remain distinct. Optional room-tone audio/generative removal deferred; do not expand them before the required evidence gate.
