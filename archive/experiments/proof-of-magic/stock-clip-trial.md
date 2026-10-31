# Stock clip trial: Teach extraction

**Date:** 2026-10-27  
**Purpose:** Smoke-test the real Muse Spark video path before a controlled learner-state experiment.

## Asset

- Pexels: [Man Assembling Lego Toys](https://www.pexels.com/video/man-assembling-lego-toys-6666449/)
- Creator: Roman Odintsov
- Source page describes a close-up of hands assembling colorful toy blocks; duration shown as 12 seconds.
- Pexels marks the clip free to use under its [photo and video license](https://www.pexels.com/license/).
- The source clip was downloaded to `/tmp/showme-stock-lego-6666449.mp4` for this local experiment. It is intentionally not committed to the repository.

## Run

- Model: `muse-spark-1.3`
- Prompt: `showme-video-analysis-v2`
- Input: one 11.61-second, 2160×3744 stock clip; converted locally to a silent 1280-pixel maximum-dimension MP4 before upload.
- Result: 3 states, 2 transitions, 3,061 input tokens, 983 output tokens.
- Local structure/reference validation: passed.
- Temporary output: `/tmp/showme-stock-lego-run2/process.json`.

## Post-hoc review

The returned process describes a small yellow element being joined to a light-grey connector, followed by a black piece being joined to the same assembly. The returned timestamps were consistent with the visible clip when spot-checked. Muse marked exact part identity and the overall build goal as uncertain rather than inventing them.

This is useful evidence that one short real video can pass through preprocessing, Meta upload/inference, structured process extraction, and local validation. It is **not** evidence of held-out state recognition: there was no paired learner clip, deliberate mistake, recovery, or preregistered answer key. A single trace also cannot establish that the observed order is a necessary dependency.

## Decision

Keep the current bounded claim: Teach can produce a reviewable process hypothesis from this clip. Do not claim that SHOWME can yet detect mistakes or recognize recovery. The next meaningful evaluation needs separate, neutral-named correct and mistake/recovery recordings of the same task, with a private answer key written before inference.
