# Veil decisions log

## Prior Veil gate (Oct 28)
Source: veil/docs/*.md and veil/artifacts/*. "observed" = saved raw API response or artifact exists;
"claimed" = stated in docs without a saved artifact I could find. All runs: synthetic fixtures only.

| Item | Status | Evidence |
| --- | --- | --- |
| SAM 3.1 accepts VIDEO (upload via /v1/files purpose=user_data, then input_video.file_id on POST api.meta.ai/v1/responses) | observed | artifacts/smoke-001/sam-video-face-raw.txt |
| SAM stream format: per frame `<Nf>obj<|box;x1;y1;x2;y2;w;h|><|mask;x;y;data=...|>`, parsed with meta-sam-parser==0.1.0; frame order not chronological; confidence null | observed | smoke-001/sam-video-face.json |
| SAM face tracked in all 180 frames of one 18 s clip | observed | smoke-001/sam-video-face.json |
| SAM text prompt "license plate" returned 0 matches (image and video); Spark-seeded box prompt worked (180 regions) | observed | smoke-001/sam-video-plate*.json |
| SAM point prompt on phone field segmented one digit; whole-box seeding fixed it | observed | smoke-001/sam-repair-track.json, live-pipeline-003 |
| Voice: POST api.meta.ai/v1/asr/transcribe, multipart (request JSON + audio WAV), returns TURN-level timestamps only, no words, no confidence | observed | smoke-001/voice-original.json |
| Voice misread spoken "202-555-0146" as "55460146" | observed | smoke-001/voice-original.json |
| Voice code-switching / Hindi / Hinglish; keyword biasing | NOT TESTED (only languageBias=[English] used) | none |
| Spark hosted `muse-spark-1.3` on /v1/responses with JSON schema; returns 0..1000 normalized boxes (pixel request was ignored; out-of-range response rejected) | observed | live-pipeline-001 |
| Spark Open (Baseten, muse-spark-open-1026) | NOT TESTED | none |
| Open-vocabulary discovery (Spark proposes arbitrary identifying things) | NOT IMPLEMENTED: prompt asks only face / license_plate / phone_number | veil/src/veil/providers/vision.py |
| Independent OCR: macOS Vision via Swift (ocr.swift); finds omitted phone Spark-only audit missed; 250 ms cadence found a 250 ms exposure the 3-frame audit missed (1 of 1) | observed, macOS-ONLY | docs/VERIFIER_BENCHMARK.md, verifier-benchmark-001 |
| Independent face detector (YuNet) | NOT IMPLEMENTED | none |
| Hero result: initial export missed printed phone; verifier caught it; single-digit repair rejected; whole-field repair passed 3-frame review | observed, ONE synthetic clip, 3 dev runs, not a benchmark | live-pipeline-001..003 |
| Tests | 63 passed (uv run --extra test pytest -q, veil/ dir, 35 s, on wip snapshot) | run 2026-11-01 |
| Cost | ~$0.27 across live runs, not reconciled to billing | live-results.json |
| Docs claims with no matching saved artifact found during this audit | "natural-editing" quality claims were already corrected once (ANTIGRAVITY_REVIEW_FEEDBACK.md); treat natural_* docs as claimed-until-rechecked | |

## SAM path
Decision (provisional, from evidence above): hosted video path. P2's "does SAM accept video" question is answered.
Still to measure: max duration/size limits, latency per clip, behaviour with 4+ concepts per clip.

## Gate clips not filmed (2026-11-01)
Decision (user): no gate clips will be created. `gate/GATE.md` stays committed as written (incl. pre-footage amendments, `e753217`)
but **cannot be scored: the gate is "NOT RUN"**. No gate verdict, G1–G4b numbers, or "pass" claim may appear in the README or demo.
Development and evaluation use the synthetic fixture (`veil/artifacts/smoke-001/input.mp4`, fictional data). Anything measured on it is
a development check, not a gate result.

## Bleep padding = 0.5 s (chosen 2026-11-01, synthetic clip only)
GATE.md says the bleep padding is the value recorded here, tuned on the synthetic clip only, never on gate clips.
Evidence: `veil/artifacts/smoke-001/input.mp4`, windowed listen run `runs/synth` (not committed; reproduce with
`veil run veil/artifacts/smoke-001/input.mp4 --run-id synth`). The windowed PII interval was [4.5, 9.5] s. Reference span for the spoken
number: onset 4.9 s from model-free energy segmentation, end 9.371 s from the fixture's `speech_end_ms`.

| padding | coverage of reference | over-cover |
| --- | --- | --- |
| 0 s | 100% | 0.53 s |
| 0.15 s | 100% | 0.83 s |
| **0.5 s** | 100% | **1.53 s** |
| 0.9 s | 100% | 2.33 s |

Choice: 0.5 s. A word cut by a 2 s window edge can be missed by both windows, so padding hedges that under-coverage; 0.5 s keeps
~1 s of the 2.5 s G4b budget free for window imprecision on other audio. Over-cover grows as 0.53 + 2 x padding, so the
largest padding that fits the budget on this clip is ~0.98 s; 0.5 s is deliberately well inside it. One clip, English
only: this is a setting, not evidence about Hinglish audio. The 2.5 s G4b threshold in GATE.md is unchanged, and the gate itself is not run.

## gate-freeze (2026-11-01)
Frozen from the `gate-freeze` tag: discover prompt `discover_v1.txt`, Spark concept cap (10) and min confidence (0.3),
dedupe threshold (85), keyframe selection, track-start rules (15 frames / earliest discovery keyframe, reversed SAM then
hold-back), temporal padding (+/-3 frames), cover padding (12 px), bleep padding (0.5 s), audit checks and the GATE.md thresholds.
Any change after gate footage is processed is reported separately as **post-gate**. Receipt layout checked at 1000 px and
360 px widths in headless Chrome (CSS-only fix; not a frozen parameter).
