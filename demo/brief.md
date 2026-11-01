# Demo brief: Veil

**CONFIG (filled from the repo; placeholders in the pasted template were empty)**
- product_name: Veil
- one_liner: Muse Spark finds what in *your* video could identify you, SAM 3.1 tracks it, Voice hears the spoken number; code redacts, re-checks the export, and lists what it could not clear.
- product_source: `./veil/web` (DemoApp, reads `public/demo/manifest.json` from a real pipeline run)
- audience: hackathon judges (Meta Global AI Developer Hackathon, Indie track; submission video must be <= 3:00)
- renderer: remotion · formats: 16:9
- must_not_say: "safe", "certified", "guaranteed", "private", "leak-free", "no competitor does this", any gate PASS (frozen gate is FAIL), real-world accuracy numbers
- **Open (see gate questions):** target length, voice mode + reference, music, brand.

## Problem (user's words)
"I filmed my street, and my name, my flat number and my phone number ended up in the video."

## Aha moment
Side by side: the input with Spark-proposed regions ("notification banner: shows the name Rohan Kulkarni") next to the output with those exact regions covered. Then the receipt says what it covered **and what it could not clear**, instead of "safe".

## Proof points -> recordable flows
1. **Open-vocabulary discovery beats a fixed list.** Held-out clips: fixed face/plate/phone/document baseline 0/4 planted leaks, with Spark 3/4 (`eval/results/final/heldout_results.md`). Flow: kinetic stat card + DemoApp overlay at t=6 s (amber Spark boxes with labels).
2. **Track + redact + re-check the export.** Flow: seek slider 6 s -> 12 s; output pane shows covers following; scroll to Findings: "cover verified in decoded output on all 557 masked frames".
3. **Abstention, not certainty.** Flow: Findings rows UNRESOLVED (license plate: 120 frames with no mask; face-like region in output) and NOT_CHECKED (cost cap / SAM stream error). Plus the verify stage rejecting SAM's mask on the code editor (OCR read code, not "KULKARNI").
4. (optional) **Spoken number in Hindi.** c3: transcript with garbled digits, mute interval.

## Real vs mocked
- Real: every value in the DemoApp comes from `runs-postgate/c2` (live Spark/SAM/Voice calls on 2026-11-01 and the original gate run). Nothing mocked.
- Footage: composited (Wikimedia Commons CC BY-SA street footage + fictional graphics). Must be stated on screen; attribution in end card.
- **Needs fixing before capture (flagged):**
  - Cost line shows "34 calls, est. $0.00": the post-gate run only counted re-run stages, and the original ledger was set aside, so this number is wrong. Fix `export_web` to sum both ledgers, or hide the cost line.
  - The verify rejection (proof 3, the best abstention moment) lives only in `verify.json`; the UI does not show it. A small UI panel is needed, or show the JSON/terminal (less pretty).
  - c3 (voice) has no export; needs `veil export-web c3`, and the UI shows one manifest at a time.
  - UI is a plain dev page (monospace, small). Fine inside a floating window with zooms; not a polished product UI.
- Honest caveats for VO/captions: composited clips; frozen gate FAIL; post-gate fixes designed after seeing failures.

Screenshots: `shots/0*.png` (2560x1440), contact sheet `shots/contact.png`.
