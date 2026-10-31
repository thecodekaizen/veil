# Antigravity — VEIL visual demonstration handoff

**Product locked.** VEIL — Detect. Redact. Verify.

> **Live core update:** detect, verify and repair endpoints now exist and have been exercised on synthetic footage. `veil/docs/PIPELINE_API.md` supersedes section 5's older missing-endpoint statements. Current development port: **8019**. Latest demonstration assets: `veil/artifacts/live-pipeline-003/`. Read `veil/docs/LIVE_EVALUATION.md` for evidence and limitations. Preserve sampled-audit language and utility warnings; never label an output zero-leak. The SDK also exposes `protect(...)` with explicit transfer/media confirmation. The temporary development server is not an uptime guarantee.


Build a striking, clear reference interface for an embeddable video privacy engine. The visual argument is a real exported video with a real missed exposure that is found and repaired. The engine remains the product. This file authorizes reference-interface design work in parallel with core integration; it does not authorize invented backend functionality.

## 1. Ownership and working rules

- Own the reference frontend in `veil/web/`, its design assets and frontend tests. Start there; do not repurpose the historical SHOWME interface in `apps/web/`.
- Codex owns `veil/src/veil/`, model adapters, engine, verification, HTTP API and SDK. Coordinate proposed contract changes in a document; do not rewrite these files silently.
- Read root `AGENTS.md`, `veil/AGENTS.md`, `veil/docs/PRODUCT.md`, `veil/docs/IMPLEMENTATION.md`, `veil/docs/MODEL_CAPABILITIES.md` and this file first. Historical product locks are superseded.
- Implement the frontend directly. The user explicitly wants delivery during this hackathon; do not stop for learning exercises or ask whether to scaffold a handler.
- Preserve other agents' dirty files. Never stage everything. Commit coherent frontend/design changes with descriptive messages, then push the current branch. Do not change repository visibility.
- Keep a small checklist in `veil/web/IMPLEMENTATION.md`: planned, implemented, verified, blocked. Include exact checks and screenshot paths. “Looks done” is not verification.

## 2. What the audience must understand in ten seconds

1. Video leaks can be visual **and** spoken.
2. VEIL covers and mutes them across time.
3. VEIL checks the **exported file** and can catch a failed redaction.

The hero moment is **a remaining phone number found in an actual export**, followed by a corrected export. Make that moment unmistakable. No opening architecture diagram, generic SaaS landing page, animated globe or dashboard.

## 3. Art direction: a precise video inspection desk

Create the feeling of a professional film inspection tool: large footage, deliberate typography, restrained controls, readable evidence. The footage should occupy most of the viewport, not sit inside a small card surrounded by empty marketing panels.

### Visual system

- Background: near-black neutral `#090C10`; panels `#12171E`; raised controls `#1B2430`.
- Main text `#F3F6FA`; secondary `#A8B5C5`; subtle borders `#2A3543`.
- Protection/selection accent: icy cyan `#69DDF3`. Potential exposure: amber `#FFBE66`. Confirmed residual requiring repair: warm red `#FF786F`. Completed operation: mint `#84E0B4`.
- Color always accompanies a label/icon; never communicate state with color alone.
- Use one strong sans family (Inter or an available system sans) with tabular numerals. Small monospace only for timestamps, IDs and code. Use local/system fonts if downloads are unavailable.
- Spacing rhythm 4/8/12/16/24/32. Corners 8–12 px, thin borders, minimal shadows. No rainbow gradients, excessive glow, glass layers or decorative emoji.
- A simple VEIL wordmark and small rectangular cover motif suffice. No logo project or asset-generation spending needed.

### Motion with a purpose

- 140–220 ms control transitions; 250–400 ms panel transitions.
- Selecting a finding seeks the video and briefly outlines its actual region. A residual finding expands into evidence and a repair action.
- Use synchronized scrubbers for paired previews; report if source/output durations differ. Do not animate detection boxes independently of real timestamps and geometry.
- The repair transition plays the corrected media and updates its evidence state only after the actual result is available.
- Respect `prefers-reduced-motion`; disable scans and spatial transitions. No scroll hijacking, custom cursor or autoplay audio.
- Never show a simulated scan as live inference progress. An indeterminate “Analyzing…” is acceptable when the backend provides no progress fraction.

## 4. One workspace, one obvious next action

Desktop target: 1440×900; review at 1280×800 and 390×844 too. No horizontal page scroll. Desktop composition:

```
VEIL  Detect. Redact. Verify.              [Recorded example / Current job]
Import ─ Detect ─ Redact ─ Verify ─ Repair ─ Export       job status
┌───────────────────────────────────────┬────────────────────────────┐
│                                       │ Selected finding           │
│        SOURCE / EXPORTED VIDEO        │ Category · timestamp       │
│        or synchronized comparison     │ Observed evidence          │
│                                       │ Protection / audit status  │
│                                       │ [one next action]          │
├───────────────────────────────────────┴────────────────────────────┤
│ timeline: Face / Plate / Visible text / Speech                       │
│ play · seek · timestamp · toggle source/export · inspect finding     │
└────────────────────────────────────────────────────────────────────┘
Evidence / verification scope                         [Download MP4]
```

Mobile: video first, compact controls, timeline, then selected finding as a normal panel. Do not cram the desktop layout into a tiny canvas.

### A. Import

Heading: **Check a video for privacy exposures.**
Supporting copy: “Find faces, plate identifiers and spoken phone numbers, then inspect the exported result.” This describes the product direction; current unsupported actions must be labeled below.

Show a clean drop target, format/size limits, and a separate **Open recorded example** action. Do not auto-upload media to Meta. Explain cloud transfers immediately before a cloud action. A file selection alone must not charge credits.

Upload CTA: **Upload video**. API upload is local, not a Meta transfer. Validation errors retain the selected file and explain the accepted limits.

### B. Detect / findings

Each finding row: category, start/end timestamp, source, status and a thumbnail or selected frame. Selecting it seeks to evidence. Provider confidence remains absent/null unless actually supplied; do not invent percentages.

Masks/covers and track boxes must be separate toggles. Source geometry overlays should not be burned into the media preview. Show “Saved inference” for archived model results and “Client-supplied timeline” for the current render API.

### C. Redact / compare

Let the exported media speak. Prefer two synchronized panes when space allows and a source/export toggle on mobile. Labels remain visible. Opaque covers are deliberate for sensitive text; do not substitute visually attractive weak blur.

CTA: **Render redacted video** when the endpoint can perform that operation. Show real output only after download or playable URL exists. If no output exists, show the waiting state, not a placeholder pretending to be the result.

### D. Verify / repair — hero surface

Headline on the recorded failed export: **A phone number is still visible.**
Evidence panel: output frame, exact available timestamp, returned reason and exposed field location. CTA **Inspect exposed frame** seeks the **export**, not the original.

Show the true sequence:
1. Initial export: printed number omitted.
2. Export inspection: number found.
3. First repair: only one digit covered; review rejects it.
4. Whole-field repair: corrected export.

This failed first repair is excellent evidence that the verifier does useful work. Do not hide it or rewrite it as first-attempt success.

For archived data, action is **View recorded repair**. Only show **Repair exposure** as a live action once a real endpoint exists. Do not play a canned animation and call it live repair.

Final label: **No exposure reported in 3 sampled frames.** Below it: “Reviewed at 00:02.000, 00:07.500 and 00:16.000. Other frames may contain missed exposures.” Local fixture coverage checks can be shown separately. Never say “100% private,” “safe to publish,” “zero leaks” or “certified.”

### E. Export / integration

Actions: **Download redacted MP4**, **Download audit receipt**. Receipt shows file hashes, audit scope, model requests, estimated API cost and limitations. Hide API secrets entirely.

A compact “Embed VEIL” drawer can show the real SDK example from `veil/README.md`. It must include the reviewed timeline argument because automatic processing is not wired yet. No fake one-line `process(id)` claim.

## 5. Actual capability and API contract — do not guess

Current working local server: `http://127.0.0.1:8018`; generated OpenAPI: `/openapi.json`; docs: `/docs`. Make backend URL configurable. This is a temporary local process, not an uptime guarantee. Run from repo `veil/` with:

```sh
python -m uvicorn veil.api.app:create_app --factory --host 127.0.0.1 --port 8018
```

Current routes:

| Route | Actual behavior |
| --- | --- |
| `POST /v1/jobs` | Multipart `video`; saves a local upload; returns JSON job with `id`, status and media metadata. No cloud inference. |
| `GET /v1/jobs/{id}` | Returns persistent local job status. |
| `POST /v1/jobs/{id}/redact` | JSON Timeline body; renders a client-supplied reviewed timeline. Synchronous request. |
| `GET /v1/jobs/{id}/findings` | Returns reviewed timeline if supplied; explicitly says detection not run. |
| `GET /v1/jobs/{id}/receipt` | Receipt after render; privacy verification explicitly not run. |
| `GET /v1/jobs/{id}/export` | Actual MP4 after successful render. |

There is no detect/verify/repair endpoint yet. Do not invent routes, mock their success, or issue paid calls directly from the browser. The Python API owns inference credentials. UI must handle 404, 409, 422 and network/render failures. Render is synchronous; do not retry the POST automatically on network timeout. Read job status before offering a deliberate retry/new job.

Current API limits: 100 MiB, up to 60 seconds and 1080p, audio stream required, constrained constant-frame-rate support. Current `Timeline` fields: duration_ms, fps, width, height, visual_tracks, audio_intervals. Read `veil/src/veil/core/models.py` for exact validated shape.

Use a same-origin development proxy or a thin server-side proxy to the Python service. Do not loosen CORS globally, duplicate media processing in JavaScript or expose arbitrary filesystem paths. Frontend must work without any model key.

## 6. Two clearly separated operating modes

**Current job:** live API upload/render/download using reviewed geometry. Never silently attach the example's coordinates to an arbitrary upload. Unsupported automatic actions show an honest disabled explanation until integrated.

**Recorded example:** inspect archived real requests and actual MP4 artifacts. Show a persistent “Recorded example · saved real inference” badge. This makes the visual demonstration buildable now without pretending to have a completed end-to-end API. When live detect/verify/repair arrive, replace the transport/data source, not the evidence semantics.

Create an explicit adapter/manifest for the recorded example. Use relative web URLs served from allowlisted copied synthetic artifacts; no `/Users/...` paths in browser code. Validate JSON before rendering it as UI content. Store local job media only in backend ignored storage, not frontend public assets. Fixture files copied into public assets must be the approved synthetic files listed below.

## 7. Evidence already available

All paths are relative to repository root:

- `veil/artifacts/smoke-001/input.mp4` — original synthetic clip.
- `veil/artifacts/smoke-001/redacted.mp4` — first export with deliberately omitted printed phone.
- `veil/artifacts/smoke-001/repaired.mp4` — failed single-digit repair.
- `veil/artifacts/smoke-001/protected.mp4` — corrected whole-field repair.
- `veil/artifacts/smoke-001/sample.jpg`, `export-check.jpg`, `repaired-sample.jpg`, `protected-2000.jpg`, `protected-7500.jpg`, `protected-16000.jpg`.
- `veil/artifacts/smoke-001/timeline.json` — face/plate geometry and audio mute.
- `veil/artifacts/smoke-001/field-repair-timeline.json` — frame-specific whole-field repair geometry.
- `veil/artifacts/smoke-001/export-visual-inspection.json`, `repaired-visual-inspection.json`, `protected-review.json` — actual output reviews. A review of one frame does not establish a time interval; do not invent a residual interval where only sample evidence exists.
- `veil/artifacts/smoke-001/protected-media-checks.json` — measured local fixture-region coverage and audio samples.
- `veil/artifacts/smoke-results.json`, `veil/artifacts/smoke-001/receipt.json`, `calls.json`, `field-repair-audit/calls.json` — outcomes and costs.
- `veil/artifacts/api-export.mp4`, `veil/artifacts/api-roundtrip.json` — actual SDK/HTTP rendering roundtrip; fresh inference not run.

Ground truth is evaluation-only: never feed `ground-truth.json` into inference, create production detection findings from it, or claim its boxes were model-detected. It may only inform clearly labeled benchmark displays.

Known limitations to preserve: one composited clip, no real-camera benchmark; SAM plate concept prompt found nothing and Spark localization seeded successful SAM tracking; Voice misread the spoken digits, requiring broad muting; final Spark review sampled three frames; same-family review can share model errors. No precision/recall benchmark or universal reliability claim yet. Estimated historical calls cost about $0.17, not a guaranteed per-video price.

## 8. Demo choreography: three minutes

| Time | On-screen action | What it proves |
| --- | --- | --- |
| 0:00–0:15 | Play synthetic source; show the face, plate, printed number and speech. | Concrete privacy exposures. |
| 0:15–0:45 | Inspect actual saved inference and temporal tracks. | Meta detection/localization, tracking and voice roles. |
| 0:45–1:10 | Play redacted export, toggle source/output. | Actual rendered MP4 and audio mute. |
| 1:10–1:55 | Find printed-number exposure; show rejected one-digit repair, then corrected output. | Output verification catches a real incomplete protection step. |
| 1:55–2:25 | Inspect final sample review plus separate all-frame fixture coverage/audio checks. | Measured evidence with stated scope. |
| 2:25–2:45 | Run SDK/HTTP render-download integration if stable; otherwise show labeled recorded roundtrip. | Engine can be embedded. |
| 2:45–3:00 | Play corrected output; download receipt. | Deliverable, limitations and reusable engine. |

Start with footage. Reserve architecture detail for a compact final drawer: SAM tracking, Voice speech timing, Spark localization/output review, FFmpeg rendering. Never narrate an archived operation as a live request.

## 9. Implementation order and acceptance

### A — Design and data contract
- [ ] Write `veil/web/DESIGN.md`: layout, tokens, typography, state matrix and responsive behavior.
- [ ] Produce an executable static layout or lightweight mockup of the workspace and repair-evidence state; keep it in the frontend, not a separate throwaway product.
- [ ] Add typed fixture adapters with provenance, sample timestamps and explicit not-run states.

### B — Recorded evidence workspace
- [ ] Play all four actual MP4 stages with correct labels.
- [ ] Findings seek to evidence; overlays follow actual frame/time geometry.
- [ ] Compare videos without drift after seek/pause; mobile uses toggle.
- [ ] Show failed repair and scoped final review truthfully.
- [ ] Downloads return the intended MP4/receipt; no broken paths.

### C — Live local integration
- [ ] Upload → read job → submit explicit reviewed timeline → render → download.
- [ ] Never reuse fixture coordinates on a different video automatically.
- [ ] Show errors, processing, interrupted and not-run states; no invented completion percentages.
- [ ] Backend unavailable state keeps recorded example accessible and clearly labeled.

### D — Finish and verify
- [ ] Keyboard-accessible controls, visible focus, captions/text alternative for important speech, readable contrast and reduced motion.
- [ ] Screenshots at 1440×900, 1280×800 and 390×844; inspect them, fix clipping/overlap, commit screenshots under `veil/web/docs/screenshots/`.
- [ ] Frontend typecheck/build/tests pass; record exact results. Tests protect mode separation, failed-repair visibility, not-run labels and download routing.
- [ ] Record a short real interaction capture or supply clear steps for the three-minute capture. Do not claim a video exists unless created.
- [ ] Update frontend README with run commands and limitations. Commit and push scoped work.

## 10. Deliver back to Codex

Report: commit hash; files changed; screenshot paths; checks run and results; which actions are live vs recorded; required backend contract additions. Include blockers explicitly. Do not ask the user to implement handlers or manually wire the UI. Build the reference experience while Codex continues core detection/verification integration.

The standard: a judge should instantly see **what leaked, when it leaked, how VEIL found it in the export, and what changed after repair**. Every visual decision should make those facts easier to see.


## Core contract addendum: denser independent OCR

The default verifier now uses three Spark samples plus bounded local OCR at 250 ms cadence. `frames` may include OCR-only timestamps; preserve the `source` label. `coverage` and `independent_ocr.sample_times_ms` state the actual local scope, separate from Spark `sample_times_ms`. Status `review_incomplete` means an independent check failed or was unavailable; it is not a passing audit. Show `check_status`, `checks_complete` and excessive-masking warnings. Historical recorded results keep their historical three-frame scope. New three-clip verifier evidence is in `veil/docs/VERIFIER_BENCHMARK.md`; do not present it as general accuracy or end-to-end repair on new scenes.


## Face-style option and new comparison asset

Core now supports **optional face blur** while keeping opaque covers mandatory for plates/phone numbers and as the default for faces. Detect payload may include `face_action: "blur"`; reviewed face tracks may use `action: "blur"`. Text tracks reject blur. Read `veil/docs/REDACTION_STYLES.md` for the contract and limitations.

Fresh variant: `veil/artifacts/face-blur-001/export.mp4`, `frame-2000.jpg`, `frame-7600.jpg`, `frame-16000.jpg`, and `receipt.json`. It has a fresh audit; do not reuse the opaque variant's receipt. You may add a clearly labeled optional face-blur choice/recorded comparison. Never label blur anonymous or leak-proof. Conservative padding remains unchanged; no polygon/contour rendering is claimed. Keep the opaque default and old evidence available. Frontend only requests the style; Python bakes the pixels.


## Real-camera hybrid demonstration and lifetime repair

Removed 2026-11-01: the Pexels office hybrid evidence (docs, scripts, `public-footage-001` artifacts) was withdrawn because its license/consent chain was not verified from a primary source. It remains in git history only.


The core now emits separate presence-bounded phone tracks with gaps; overlays must honor their actual frame regions rather than extending a box for the entire video. No new frontend processing logic is needed.

## Priority update — natural-editing experiment split (28 October)

Read `ANTIGRAVITY_NATURAL_EXPERIMENTS.md` before continuing. The user now assigns Antigravity dataset screening and independent visual-quality experimentation, not just frontend work. Follow its exclusive ownership boundaries and deliver exact proposed clips before running a new benchmark. Codex continues core tracking, fallback and exported-file privacy evaluation. The six-case natural-editing gate has NOT passed; today's objective is an evidence-based submission decision.
