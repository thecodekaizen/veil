# Antigravity: natural-editing experiments and today's decision

Assigned by the user on 28 October 2026. This supplements ANTIGRAVITY_VEIL.md. Priority NOW is experiment evidence, not reference-UI polish. VEIL remains the product. Implement your assigned experimental work directly; do not return exercises for the user to implement.

## Objective

Help decide TODAY whether VEIL Natural Editing is credible for submission. We need actual playable outputs, detected failures and visual-quality evidence, not a new design proposal. Work in the existing repository `/Users/thecodekaizen/Code/Projects/hackathons/veil`; product lives in `veil/`.

Read AGENTS.md, veil/AGENTS.md, veil/docs/NATURAL_EDITING_CHECKPOINT.md, veil/docs/DATASET_EVALUATION.md, veil/docs/PUBLIC_CAMERA_RESULTS.md. Baseline core checkpoint is commit `71f205a` (50 local tests passed). Preserve historical dirty `apps/web/` and other agent files. Do not reset/stash another agent's work or overwrite prior experiments.

## Work split and exclusive ownership

**Antigravity owns**
- `veil/docs/NATURAL_DATASET_SELECTION.md`
- `veil/docs/NATURAL_VISUAL_REVIEW.md`
- `veil/scripts/evaluate_natural_quality.py` (evaluation only; no renderer code)
- `veil/artifacts/natural-review-20261028/` (derived comparison media, metric JSON, review sheets, failed-output gallery; source media only when redistribution is permitted)
- Existing `veil/web/` only if a small existing recorded-example viewer helps review; no frontend expansion before experiment outputs.

**Codex owns**
- `veil/src/veil/` renderer, tracking, privacy audit, job/API/SDK contracts.
- Core tests, fixture generation and candidate export runs.
- Privacy acceptance, core benchmark evidence and final consolidated decision.

Do not modify core source, tests, original fixtures, root README, shared implementation/checkpoint documents, or Codex's artifact directories. If a renderer defect blocks review, record its case/frame and notify the user with a precise request for Codex. Commit only your owned files; inspect staged paths before committing. Never commit source datasets with unclear redistribution terms.

## Track A — select usable video evidence, not just dataset names

First deliverable: a concrete shortlist, ideally within 45 minutes. Follow the supplied dataset request: show six exact proposed clips BEFORE new benchmark implementation/model runs. Research/download screening is allowed; a proposed slot is not a downloaded clip.

For every candidate record:
- Official dataset/source and exact clip filename/ID and download URL.
- Access verified? direct/public, registration, signed agreement, or unavailable.
- Source byte size and proposed start/end crop; source fps/resolution; SHA256 after download.
- License/terms and attribution with official URLs. Separate local evaluation, public redistribution and third-party cloud transfer permission. Unknown means unknown.
- Participant consent where relevant. No real stranger's identifiers uploaded to Meta under the project's synthetic/consented-media policy.
- Available annotations: plate boxes? corners? tracked identity? person silhouettes only? none? Do not assume.
- What requires manual annotation and how many minutes it would take.
- One contact sheet confirming the actual target is visible and usable.
- Whether it belongs in a private research diagnostic, public demo, or neither.

Priority capabilities: static plate, moving/perspective plate, camera movement, brief occlusion/reappearance, angled screen, difficult lighting. Do not force all six from public datasets if access/permissions make them unsuitable; identify explicit gaps rather than relabeling generated animation as natural footage. User-recorded fake-data screen clips are REQUESTED/UNAVAILABLE until supplied, never silently mark them ready. Do not ask for another LEGO video.

Sources to screen:
- BDD100K: https://bdd-data.berkeley.edu/ and https://github.com/bdd100k/bdd100k ; verify actual download access/terms and plate annotations before selecting.
- LSVTD: https://davar-lab.github.io/dataset/lsvtd.html ; publisher lists 129 clips, XML labels and CC BY-NC-SA 4.0. Check linked access; do not email authors without user authorization.
- PEViD-UHD: https://www.epfl.ch/labs/mmspg/downloads/pevid-uhd/ ; 26 13-second sequences, consent for research, person silhouette labels. This is not established plate/screen ground truth. Prefer SD/HD for screening; current engine accepts <=1080p, so do not claim native 4K support.
- CoC: https://zenodo.org/records/21790608 ; official record currently marks files RESTRICTED and non-commercial research/educational terms. Do not wait for access or imply it is immediately downloadable.
- Existing CC BY 4.0 generated plate archive is local at `/Users/thecodekaizen/Documents/ChatGPT/Hackathons/veil/artifacts/private/datasets/ukrainian-plates/source.zip`; cropped images only. Animation made from these remains synthetic, not real temporal validation.

These notes are screening observations, not a full rights clearance. Do not send new media to cloud services or accept license agreements on the user's behalf.

## Track B — evaluate existing output visually NOW, independently

While access is checked, inspect actual existing videos:
`veil/artifacts/natural-surface-001/`
- `original.mp4`
- `opaque.mp4`
- `natural.mp4` — per-frame fixture corners, not measured tracking.
- `tracked/natural-tracked.mp4` — one initial manual quad + LK/RANSAC, protective fallback boxes still fixture-authored.
- `fallback.mp4` — two deliberately missing geometry frames trigger opaque fallback.
- `comparison.mp4`, `comparison.jpg`, all-frame review sheets.
- `tracked/geometry.json`, `tracked/tracking.json`, `tracked/results.json`, `quality.json`.

These are ONE synthetic development case. Do not count each export as a separate case or use it as a held-out benchmark. Existing 72-frame OCR clearance does not mean beautiful, leak-proof or independently validated on natural footage.

Build an evaluation-only script that accepts source/output video paths and optional evaluation geometry. Read actual exported bytes. Never call model APIs. Produce:
1. Playability/frame count/duration checks and explicit timing differences.
2. Side-by-side comparison video and representative full-frame/contact sheets with labels.
3. Frame-specific excessive blackout diagnostics.
4. Edited-area and differences outside intended region, with codec tolerance and clear units.
5. Geometry error against independent labels WHEN AVAILABLE. Otherwise mark unavailable; do not score a track against itself.
6. Temporal difference/warp diagnostics only with documented motion estimation limitations; do not call raw brightness change flicker without alignment.
7. Failure gallery with case, exact frame/time, visible defect, severity, and whether fallback was used.

Inspect clips during playback, not just selected stills. Report observed edge halos, floating appearance, texture instability, drift, scene damage and fallback harshness honestly. The current generated vehicle is a mechanics fixture, not creator-quality footage. If no actual independent reviewers participate, human preference = NOT RUN. Your own visual review may be reported as agent review, not a blinded human panel. Never invent votes or scores.

## Review sheet and blinded preference protocol

Prepare a randomized A/B form and hidden mapping for baseline versus replacement, without pretending it has been conducted. Four short questions: naturalness, distraction, temporal stability, willingness to publish. Record case/order and actual reviewer responses if the user supplies them. Do not contact reviewers externally without authorization. Majority preference remains pending without votes.

## Shared evidence contract

For any selected case write a small manifest in your artifact directory:
```
{
  "case_id": "unique_id",
  "source": {"dataset": "...", "clip_id": "...", "url": "...", "sha256": null},
  "access_status": "verified|pending|restricted",
  "permissions": {"local_evaluation": "unknown", "public_demo": "unknown", "cloud_transfer": "unknown"},
  "crop": {"start_s": null, "end_s": null},
  "annotations": {"available": [], "missing": []},
  "readiness": "proposed",
  "limitations": []
}
```
Use null for unknown values. This is evaluation metadata only. Exact original identifiers and frame labels stay in a separate evaluation-only file; never insert them into model prompts or tracking initialization beyond explicitly disclosed manual first-frame corners. Do not change production schemas to match this manifest.

## Today's acceptance decision

Natural-editing gate remains at least FOUR of SIX fixed cases visually acceptable without per-frame manual repair, with no known original-value leak in any accepted output, no unexpected near-full-frame blackouts, and actual blinded preference evidence if reviewers are available. One synthetic success cannot satisfy it. Missing footage or reviewers are missing evidence, not passes. Do not relax thresholds after seeing results.

Report three separate recommendations:
- Current demonstrated redaction/verification/repair baseline: can it support an honest submission demo?
- Natural-editing feature: GO / NO-GO / INSUFFICIENT EVIDENCE under the six-case gate.
- Top-prize competitiveness: UNKNOWN unless justified; never promise winning.

## Return handoff

Deliver exact proposed clips/terms first, then your script, actual derived videos, review report, failure gallery, commands/results, commit hash and blockers. No changes to Codex-owned source. Record whether each result is VERIFIED, FAILED, UNTESTED or UNKNOWN. Work on evidence now; postpone marketing copy and visual polish.

## Core integration update — continue your independent evaluation

Read `veil/docs/NATURAL_API.md` and `veil/docs/NATURAL_INTEGRATION_RESULTS.md`. Local server port 8020 now supports opt-in natural jobs and review/receipt/download. New actual SDK/HTTP evidence is under `veil/artifacts/natural-api-*` and `veil/artifacts/natural-meta*-001`. Source/candidate/final checks, per-track decisions and actual comparison videos are available. Existing default API remains compatible; natural mode is NOT general-privacy or visual-quality clearance.

The user explicitly chose **proceed with available footage; mark the self-recorded screen case missing**. Do not request another capture or fabricate it. Keep it missing unless suitable already-available authorized footage is found and clearly classified. These new core runs are development repeats/diagnostics, NOT six cases. Focus your time on exact clip access/terms and honest playback review.

## Required review corrections

Read `ANTIGRAVITY_REVIEW_FEEDBACK.md` before committing the dataset shortlist. Codex measured a portrait-metadata mismatch and HTTP 404 in a claimed verified URL, and found unsupported consent/sequence-name assertions. Correct those claims in your owned files; do not count them as verified footage. Continue quality evaluation while access gaps remain explicit.
