# Veil test gate (preregistered)

Written and committed BEFORE any model runs on gate clips. Thresholds are frozen once committed.

Gate clips: 3 clips, 20–30 s each, staged set, fictional data only.
Planted: (1) delivery box with a fictional address label, (2) phone notification showing a
fictional name, (3) door nameplate ("KULKARNI — 12"), (4) one more visual leak of my choice
(society name board "SUNSHINE CHS — WING B"), (5) a fictional 10-digit phone number spoken in Hinglish.
Safe controls: code in an editor, a book cover, a product logo.

Amended before any gate footage existed: face reflection → door nameplate.

`in_baseline` assignments (baseline prompts = face, license plate, phone screen, paper document; when in
doubt, true): box label = true (paper document); phone notification = true (phone screen); society name
board = false; door nameplate = false.

## PASS only if ALL hold

**G1 Discovery.** Spark-proposed concepts cover >= 3 of the 4 planted visual leaks, including
>= 1 with `in_baseline=false`. "Covers" = a mask of that concept has IoU >= 0.5 with the leak's
`ref_box` at the `ref_box` timestamp (+/- 2 frames). Only concepts with `source="spark"` count.

**G2 False flags.** <= 1 safe control is matched by any Spark-proposed concept (same IoU rule).

**G3 Tracking.** For each planted visual leak that is covered, a mask exists in >= 95% of frames
inside its `visible_ranges`.

**G4a Detection.** The planted spoken number produces a phone-like PII hit: >= 6 digits from
>= 4 consecutive digit tokens after normalization (spelled-out digit words in English, Hindi or
Marathi count as digit tokens). Exact digits are NOT required. Digit accuracy (exact-match and
per-digit edit distance against the labelled `digits`) is a reported metric, not a gate.

**G4b Localization.** The bleep interval covers 100% of the labelled spoken span
(`audio.t_start`..`audio.t_end`), and the total over-cover is <= 2.5 s.
- "Bleep interval" = the union of the intervals the redact stage would mute: each PII interval from
  `listen.json`, padded by the bleep padding.
- Bleep padding = the value chosen and recorded in docs/decisions.md, tuned on the synthetic clip only,
  never on gate clips. Thresholds unchanged.
- "Total over-cover" = total seconds of the bleep intervals in the clip that fall outside the
  labelled span (including any bleep not tied to the planted number).
- The scorer records the precision method used to obtain PII timing: `streaming` | `windowed` | `turn`.

**G5** (evaluated after redact + audit exist; not a kill criterion). After redaction, independent
OCR finds none of the planted text and the independent face detector finds no face in planted
ranges; anything else is listed UNRESOLVED, never hidden.

Thresholds are frozen. Proposed changes go under "Proposed changes (not applied)" below.
If G1–G4 fail: stop Veil; fallback = Andaaz gate at Sunday breakfast.

## Measurement notes (fixed before the first gate run)
- IoU is computed in source-video pixel coordinates at the frame nearest the `ref_box` time.
- Frame indexing is 0-based on the normalized video at the clip's fps.
- Labels are written once, committed, and never edited after the first gate run. `clip_sha256` in each
  label file must match the clip file or the scorer aborts.
- Evidence recorded per criterion: matched concept, IoU, coverage %, detected digits, timing error,
  artifact paths.

## Known risk recorded before the run (not a threshold change)
A 2026-11-01 smoke test (`docs/api_notes.md`) on one synthetic English clip found Voice returns turn-level
timestamps only. Turn timing did not cover the whole number; 2 s / 0.5 s windowed transcription did,
with ~2.25 s over-cover before padding. G4b may therefore be marginal on Hinglish audio. This is expected
information, not grounds to change the bar.

## Proposed changes (not applied)
(none)
