# Veil demo v4: story-first storyboard (revised, awaiting voice pick + render)

Target 2:00–2:20 (rules: three-minute demo video). Every caption, highlight, zoom and cut is placed on Whisper word timestamps of the
final narration. Footage is real pipeline output on composited clips with fictional data. A small persistent caption from 0:00
says "Demo clips: composited, fictional data". No blur anywhere: Veil uses opaque covers, or natural mode. Nothing about speed.

Camera: zooms are kept, but each starts ON the word that names its target, eases in over 500 ms (ease-in-out), holds >= 1.8 s,
and never zooms back out: the shot ends with a hard cut. One zoom per shot, none during transitions or cursor travel, cursor
hidden. Small-text shots (mask check, findings, ledger, Glimmer, proof) use a TIGHT FIXED CROP from their first frame, so key text
is >= 28 px tall at 1080p (readable on a phone) without any camera move.

Audio: narration (Kokoro, voice picked by ear) is the loudest element. Licensed background music is ducked about 20 dB under speech
and rises a little in pauses. Final master -14 LUFS integrated, true peak <= -1 dBTP; checked: narration >= 15 dB above music while speaking.

## 0:00–0:25 (the part a judge decides on)

| # | Time | Narration | On screen | Camera | Reason | On-screen text |
|---|---|---|---|---|---|---|
| 1 | 0:00–0:04 | "This street clip is about to be posted." | c2 input from 5 s, full frame, playing | static | n/a | **About to be posted.** · small, persistent: *Demo clips: composited, fictional data* |
| 2 | 0:04–0:08 | "It shows a stranger my full name, and my flat number." | same clip; amber box on the notification on "full name", on the door plate on "flat number" | highlight boxes (no zoom: both must stay visible) | boxes land on the words that name them | **It leaks: ① a full name ② a flat number** |
| 3 | 0:08–0:15 | "A standard redaction tool looks for faces and plates. It covers one car's plate, and misses both." | **real** fixed-class export of the same run (`output_fixed_classes.mp4`: only the standard-class covers, here one car's plate); the two boxes turn red, "still exposed" | zoom to the covered car plate on "one car's plate", hold; hard cut on "misses both" to the wide frame with both red boxes | the zoom shows what the standard tool did cover; the cut back shows what it missed | **Standard detection (faces · plates · screens · documents): both still exposed** · small: *0 of 4 across 3 test clips* |
| 4 | 0:15–0:25 | "Veil finds what identifies you in this specific video. Not just faces and plates. Then it covers it, before you post." | wordmark "Veil" once (0:15–0:17); then side by side: **Standard detection** (left) vs **Veil** (right, the real export) | zoom on the right pane's notification + door plate on "covers it", hold | "covers it" = the covers now in frame | **Veil · finds what identifies you in this video, not just faces and plates** |

5-second test (muted, 0:00–0:05): a street video under "About to be posted.", then two amber boxes on a name and a door plate
under "It leaks: ① a full name ② a flat number". By 0:15 the muted viewer also sees "Standard detection: both still exposed".

## 0:25–end

| # | Time | Narration | On screen | Camera | Reason | On-screen text |
|---|---|---|---|---|---|---|
| 5 | 0:25–0:33 | "Muse Spark reads the clip, and proposes what could identify you, with a reason." | desk (live site), compare stage, playing | zoom to the notification + Spark's verbatim reason callout on "with a reason" | the reason is on screen when spoken | **1 · Find: Muse Spark proposes, with a reason** |
| 6 | 0:33–0:39 | "SAM 3.1 tracks each one, through every frame." | desk tracks panel | zoom to the track bars on "every frame" | bars span the clip | **SAM 3.1 tracks it through every frame** |
| 7 | 0:39–0:52 | "It listens, too. Muse Voice hears a phone number said in Hindi, and Veil mutes it." | desk c3: transcript + mute bar | zoom to the Devanagari transcript on "Hindi"; hard cut on "mutes" to the tight crop of the red mute bar | the Hindi words / the mute | **2 · Listen: spoken number, Hindi → muted** |
| 8 | 0:52–1:00 | "Then Veil audits its own export." | desk verdict banner (tight crop): 5 COVERED · 2 UNRESOLVED · 0 NOT CHECKED | static | n/a | **3 · Audit the exported file** |
| 9 | 1:00–1:10 | "It reads every mask with OCR. Here, SAM grabbed a code panel, so Veil threw that mask out." | mask-check panel, tight fixed crop | zoom to the REJECTED row on "threw that mask out" | it is the thrown-out mask | **Wrong mask caught: OCR read code, not the name** |
| 10 | 1:10–1:18 | "Every finding ends covered, unresolved, or not checked. Never a blanket 'all clear'." | findings with the Unresolved filter on, tight crop | zoom to the two UNRESOLVED rows on "unresolved" | the word and the rows match | **COVERED · UNRESOLVED · NOT CHECKED** |
| 11 | 1:18–1:28 | "Prefer no black boxes? Natural mode swaps in fictional names, and runs the audit again." | desk Natural toggle; the divider sweeps across the notification (recorded, not a camera move) | zoom to the notification ("Aarav Sharma") on "fictional names" | the fictional name is in frame | **Natural mode: fictional text · audit: 0 original words left** |
| 12 | 1:28–1:40 | "I planted four private details across three test clips. Standard detection found none." | proof card, tight: test set named; left column "Standard detection: 0 of 4" | static | n/a | **Test set: 3 composited street clips · 4 planted details** · **Standard: 0 of 4** |
| 13 | 1:40–1:52 | "Across three full runs, Veil found eleven of twelve. In one run it missed a parcel label, and its audit didn't catch it either." | same card, right column: "Veil: 4/4 · 3/4 · 4/4 → 11 of 12"; the 3/4 cell outlined red "missed: parcel label · audit didn't flag it" | static | n/a | **Veil: 4/4 · 3/4 · 4/4 = 11 of 12** · *one miss, not caught by the audit* |
| 14 | 1:52–2:02 | "Discovery also runs on Muse Glimmer, right on this laptop. The frames never leave it." | Glimmer card, tight: local command, verbatim proposals, "c2: found both · didn't flag the code panel" | zoom to "● this laptop · no upload" on "never leave it" | the privacy point is the line in frame | **Open weights: Muse Glimmer, local · c2: 2 of 2 found** |
| 15 | 2:02–2:12 | "Veil. Find what identifies you, before you post." | END on the "after" frame (c2 natural export), wordmark, both URLs, music credit; hold 1.5 s | static | n/a | **Veil · thecodekaizen.github.io/veil · github.com/thecodekaizen/veil (full results, incl. failures)** |

## Facts behind every claim

- "covers one car's plate, and misses both": `runs-rep/r1/c2/output_fixed_classes.mp4` (standard-class covers only, same run: `baseline-license-plate`, 227 of 625 frames). Name and door plate are uncovered in every frame.
- "0 of 4 across 3 test clips": `eval/results/final/heldout_results.md` (baseline-only 0/4).
- "4/4 · 3/4 · 4/4 = 11 of 12": `gate/repeats/r1-r3/GATE_RESULT.md` (r1 4/4, r2 3/4, r3 4/4).
- "missed a parcel label, and its audit didn't catch it": r2 missed c1/L1 (delivery-box address label). r2's c1 audit: the output OCR check flags phone-like digit runs only, so the label (a name and address; "400099" is too short) was not flagged. The UNRESOLVED items on that clip are face-detector hits elsewhere. Checked 2026-11-01.
- Mask check, natural audit, Glimmer: `runs-rep/r1/c2/verify.json`, `natural.json`, `eval/glimmer/summary.md`.
- Deliberately not in the video: processing time (median ~18 min of model calls per 25-s clip; it's in the README).
