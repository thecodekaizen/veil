# VEIL Natural Editing: Visual Quality Review & Failure Analysis

**Date**: 28 October 2026  
**Author**: Antigravity (Visual Experiments & Dataset Screening Owner)  
**Status**: Independent Evaluation on Exported Media Bytes  
**Repository**: `veil/` (multimodal video privacy engine)  
**Evaluation Script**: `veil/scripts/evaluate_natural_quality.py`  
**Review Artifacts Directory**: `veil/artifacts/natural-review-20261028/`  
**Baseline Test Checkpoint**: Commit `71f205a` / `81ebb59` (61 tests passed)  

---

## 1. Executive Summary & Review Scope

This independent visual and integrity review evaluates exported MP4 media bytes from the first development cycle (`veil/artifacts/natural-surface-001/`), fault-injection diagnostics (`veil/artifacts/natural-failure-001/`), and recent API integration runs (`veil/artifacts/natural-api-*/`):
- `original.mp4`: Source video with planted plate `2025550146` (640×360 @ 12 fps, 72 decoded frames, 6.000 s).
- `opaque.mp4`: VEIL baseline opaque cover redaction (72 decoded frames).
- `natural.mp4`: Fixture-authored per-frame homography replacements (72 decoded frames).
- `tracked/natural-tracked.mp4`: Optical-flow (LK) + RANSAC tracking initialized from frame 0 (72 decoded frames).
- `fallback.mp4`: Deliberately omitted geometry at frames 24–25 triggering opaque cover fallback.
- `natural-failure-001/rejected-candidate.mp4`: 110-pixel shifted quadrilaterals with expanded support boxes.
- `natural-api-occlusion-001/downloaded.mp4`: Derived full occlusion across frames 24–35.

### Key Visual Findings & Verdict:
1. **Geometric Tracking on Controlled Synthetic Fixtures**:
   - On the synthetic vector-graphic fixture, LK tracking achieves a **mean corner error of 0.72 px** and a maximum corner error of **1.85 px** against withheld ground truth.
   - *Limitation*: The synthetic canvas has rigid linear translation and zero motion blur, specular glare, auto-exposure changes, or rolling shutter distortion. Real-camera tracking behavior remains unverified.
2. **Visual Defect Profile**:
   - **Boundary Seam & Aliasing**: The 1-pixel outer rim blend leaves visible aliasing along the replacement perimeter (`failure_gallery/defect_02_edge_boundary_seam.jpg`).
   - **Flat Illumination**: Scalar illumination gain ($0.96\times$) scales RGB uniformly, failing to model real-world directional lighting, specular highlights, or ambient environmental reflections (`failure_gallery/defect_03_flat_illumination_f35.jpg`).
   - **Fallback Harshness**: In `fallback.mp4`, frames 24–25 abruptly flash a solid black box into the scene for 166 ms, creating a high-contrast strobe effect (`failure_gallery/defect_01_fallback_pop_f24.jpg`).
   - **Occlusion Tracking Failure**: In `natural-api-occlusion-001`, optical flow fails during a 12-frame occlusion and does not recover after the target reappears, falling back permanently to opaque boxes for the remaining 48 frames.
3. **Integrity & Fault Injection**:
   - In `natural-failure-001/rejected-candidate.mp4`, mathematically valid homographies displaced by 110 px satisfied the renderer's protective containment checks while **exposing original plate digits across 72/72 frames**. The candidate was rejected solely by downstream exported-pixel OCR, confirming that geometric validity alone cannot guarantee privacy.
4. **Human Preference Status**:
   - **NOT RUN**. No independent human reviewers were surveyed today. The visual observations below represent assistant inspection during continuous video playback. No synthetic votes or scores have been fabricated.

---

## 2. Quantitative Measurement Ledger

The metrics below were computed directly from decoded exported video frames by `veil/scripts/evaluate_natural_quality.py` without invoking model APIs:

| Metric | Target / Unit | Baseline Opaque (`opaque.mp4`) | Tracked Natural (`natural-tracked.mp4`) | Fallback Run (`fallback.mp4`) | Fault Candidate (`rejected-candidate.mp4`) |
|---|---|---|---|---|---|
| **Decoded Frame Count** | 72 frames | 72 | 72 | 72 | 72 |
| **Video Duration** | 6.000 s | 6.000 s | 6.000 s | 6.000 s | 6.000 s |
| **Duration Delta vs Source** | 0.000 s | 0.000 s | 0.000 s | 0.000 s | 0.000 s |
| **Length Mismatch Detected** | False | False | False | False | False |
| **Blackout Frames (>95% black)** | 0 frames | 0 | 0 | 0 | 0 |
| **Mean Outside-Region Abs Diff** | 0–255 scale | 1.84 / 255 | 1.86 / 255 | 1.85 / 255 | 1.88 / 255 |
| **Max Outside-Region Abs Diff** | 0–255 scale | 1.95 / 255 | 1.97 / 255 | 1.96 / 255 | 2.01 / 255 |
| **Mean Edited Frame Fraction** | fraction (0–1) | 0.0986 (9.86%) | 0.0770 (7.70%) | 0.0782 (7.82%) | 0.0812 (8.12%) |
| **Mean Corner Error (px)** | pixels | N/A (box cover) | **0.722 px** | N/A (per-frame fixture) | **110.0 px** (seeded fault) |
| **Max Frame Corner Error (px)** | pixels | N/A | **1.852 px** | N/A | **110.0 px** |
| **Temporal Patch Diff (0–255)** | 0–255 scale | 0.0 (static box) | **2.42 / 255** | **2.88 / 255** | **4.15 / 255** |
| **Original Identifier OCR Findings** | 0 findings | **0** | **0** | **0** | **72 (100% leak)** |
| **Applied Strategy Distribution** | 72 frames | 72 opaque | 72 natural | 70 natural, 2 opaque | 72 invalid natural |

*Technical Note on Metrics*:
- **Outside-Region Difference**: The mean absolute difference of ~1.86/255 outside the dilated edit boundary is consistent with re-encoding differences, but does not establish their sole cause or prove zero damage outside the edit.
- **Temporal Patch Difference**: This measures unaligned pixel variation across normalized consecutive homography patches. It reflects raw surface appearance changes; it does not decouple vehicle acceleration from lighting, and is not an aligned optical-flow flicker measurement.

---

## 3. Failure Gallery & Visual Inspection Details

Artifacts located in `veil/artifacts/natural-review-20261028/failure_gallery/`:

### Defect 1: Fallback Harshness (Jarring Strobe Pop)
- **Artifact**: `defect_01_fallback_pop_f24.jpg`
- **Occurrence**: `fallback.mp4`, frames 24–25 (timestamps 2000 ms to 2083 ms).
- **Observed Behavior**:
  - Frames 0–23 display the light-colored synthetic `DEMO` plate texture.
  - At frame 24, geometry is withheld; the engine instantly swaps to an enlarged solid black opaque rectangle.
  - At frame 26, geometry resumes; the engine abruptly swaps back to the light textured plate.
- **Visual Impact**: Severe visual discontinuity. During playback, the 2-frame blackout functions as a high-contrast flash/strobe that immediately draws viewer attention to the redacted region.
- **Severity**: **HIGH**. Aesthetic improvement needs a separately validated opaque treatment. Do not crossfade a protective cover over exposed original text: partially transparent frames could reveal it.

### Defect 2: Boundary Seam Aliasing & Edge Halos
- **Artifact**: `defect_02_edge_boundary_seam.jpg`
- **Occurrence**: `natural.mp4` and `natural-tracked.mp4`, persistent across frames 0–71.
- **Observed Behavior**:
  - The renderer implements an interior overwrite with a 1-pixel outer bilinear rim blend.
  - On angled surfaces, the boundary of the warped quadrilateral exhibits subtle stair-stepping (pixel aliasing) against the dark vehicle bumper.
- **Visual Impact**: The replacement does not feel organically embedded into the scene; it appears as a distinct 2D sticker floating slightly in front of the vehicle plane.
- **Severity**: **MEDIUM**. Requires a multi-scale Gaussian edge blur or Poisson gradient blending along the perimeter quad mask.

### Defect 3: Flat Scalar Illumination & Lack of Environmental Response
- **Artifact**: `defect_03_flat_illumination_f35.jpg`
- **Occurrence**: Persistent across all natural replacement frames.
- **Observed Behavior**:
  - Illumination matching is currently a single scalar multiplier (`gain = 0.96`), clipped to $[0.7, 1.3]$.
  - The replacement texture maintains completely uniform planar shading.
  - The vehicle body, by contrast, exhibits subtle gradient shading from the simulated sky and road.
- **Visual Impact**: Lack of specular highlights, environmental reflections, or directional shading breaks the illusion of natural photographic capture.
- **Severity**: **MEDIUM**. Acceptable for utilitarian compliance, but visibly artificial for creator-facing production.

### Defect 4: Seeded Localization Leak Under Mathematically Valid Homography
- **Artifact**: `defect_04_mislocalized_quad_leak_f0.jpg`
- **Occurrence**: `natural-failure-001/rejected-candidate.mp4`, frames 0–71.
- **Observed Behavior**:
  - In `run_surface_failure_check.py`, quads were shifted 110 px horizontally while fixture protective support boxes were widened.
  - The OpenCV homography transformation was mathematically valid and inverted cleanly.
  - The replacement texture was stamped 110 px to the right of the real plate, leaving the original leading digits (`"2025"`) fully visible in the video frame.
- **Visual Impact & Privacy Breach**: Catastrophic privacy failure if evaluated on geometric validity alone.
- **Engine Recovery**: The native macOS exported-pixel OCR detected `"2025"` in 72/72 frames, rejecting the candidate and triggering an automatic full-sequence fallback to opaque cover.
- **Severity**: **CRITICAL** (Geometry alone is NOT privacy; exported-pixel verification is mandatory).

### Defect 5: Permanent Fallback on Brief Occlusion
- **Occurrence**: `veil/artifacts/natural-api-occlusion-001/downloaded.mp4`, frames 24–71.
- **Observed Behavior**:
  - Target vehicle is occluded by an obstacle across frames 24–35.
  - Tracking loses features and appropriately reverts to opaque cover at frame 24.
  - When the plate reappears at frame 36, tracking **does not automatically re-detect or recover**. Frames 36–71 remain covered by solid black opaque boxes.
- **Visual Impact**: The natural replacement fails to persist through ordinary real-world occlusions, behaving identically to opaque redaction for the remainder of the clip.
- **Severity**: **HIGH** (Precludes automated natural editing on dynamic camera footage).

---

## 4. Blinded A/B Preference Protocol Specification

To prevent bias and conform to the project working agreement, human preference testing cannot rely on informal developer impressions. The following protocol is formalized for future reviewer panels:

### Protocol Design
- **Reviewer Panel Target**: 5 independent participants blinded to the underlying pipeline.
- **Stimulus Pair**: Randomized Presentation Order (A vs B) of the same source clip:
  - Option 1: Standard VEIL Opaque Redaction (`opaque.mp4`)
  - Option 2: VEIL Natural Tracked Surface Replacement (`natural-tracked.mp4`)
- **Review Form Questions** (Scored on 1–5 Likert Scale or Binary):
  1. *Naturalness*: "How natural does the edited region appear in the context of the overall video?" (1 = Completely artificial/obtrusive, 5 = Indistinguishable from natural scene)
  2. *Distraction*: "Did the edit distract your attention away from the main subject of the clip?" (1 = Highly distracting, 5 = Not distracting at all)
  3. *Temporal Stability*: "Did you notice any unnatural flickering, wobbling, or popping during playback?" (1 = Severe jitter/popping, 5 = Completely stable)
  4. *Willingness to Publish*: "Would you feel comfortable publishing this video publicly?" (Yes / No)

### Blinded Mapping Sheet (Pre-Registered)
| Test Case ID | Presentation Option A | Presentation Option B | True Identity of Option A | True Identity of Option B | Reviewer Preference |
|---|---|---|---|---|---|
| `trial_01_synthetic_car` | Clip_X_091 | Clip_Y_442 | `opaque.mp4` | `natural-tracked.mp4` | **NOT RUN** |
| `trial_02_synthetic_fallback` | Clip_X_108 | Clip_Y_831 | `fallback.mp4` | `opaque.mp4` | **NOT RUN** |

**Current Status**: **NOT RUN**. Zero external human votes have been collected today. In compliance with `ANTIGRAVITY_NATURAL_EXPERIMENTS.md`, human preference must be reported as **NOT RUN**, not estimated or simulated.

---

## 5. Three Explicit Acceptance Recommendations

In accordance with the hackathon criteria and `ANTIGRAVITY_NATURAL_EXPERIMENTS.md`:

### 1. Current Redaction / Verification / Repair Baseline
**Verdict**: **GO FOR HONEST SUBMISSION DEMO**
- The core VEIL baseline (multimodal detection, opaque bounding-box redaction, SAM tracking, face-only blur, lossy codec repair, and native macOS exported-pixel verification) is robust, tested (61 passing unit/integration tests), and fully grounded in reproducible telemetry.
- It demonstrates bounded exported-media checks and repair on controlled fixtures, without a privacy guarantee or established generalization.

### 2. Natural-Editing Feature
**Verdict**: **NO-GO / INSUFFICIENT EVIDENCE (Under the 4/6 Gate)**
- **Gate Status**: Requires at least 4 of 6 fixed cases visually acceptable on real camera footage without per-frame manual repair.
- **Observed Reality**:
  - We have **one** synthetic 640×360 development clip (`natural-surface-001`).
  - Zero real-world natural camera clips are fully annotated, tracked, and verified today.
  - Fallback transitions exhibit harsh 2-frame strobe popping (`defect_01`).
  - Brief occlusions result in permanent tracking loss and permanent reversion to opaque boxes (`defect_05`).
  - Planar homographies leak data when tracking drifts unless caught by downstream OCR (`defect_04`).
- **Recommendation**: Natural editing should be presented as an **experimental opt-in research preview**, clearly labeled as synthetic-surface replacement under controlled geometry. It must **NOT** be promoted as the primary production redaction mode for arbitrary public footage.

### 3. Top-Prize Competitiveness
**Verdict**: **UNKNOWN**
- Hackathon evaluation criteria prioritize end-to-end multimodal reliability, verifiable privacy receipts, independent inspection, and honest reporting of limitations over fragile generative demos.
- Presenting a rock-solid, fully verified core privacy engine with candid documentation of experimental boundaries is vastly superior to presenting a flaky generative inpainting feature that hallucinates or leaks identifiers during live jury testing.
