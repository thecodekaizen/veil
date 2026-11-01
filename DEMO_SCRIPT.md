# Demo script (3:00 target, 2:50 real)

Use the post-gate c2 run (`runs-postgate/c2`, exported to `veil/web/public/demo`). Say that results were produced by the real pipeline beforehand; run one live command on screen.

| Time | Screen | Say |
|---|---|---|
| 0:00-0:15 | c2 clip playing: street, notification "Rohan Kulkarni", gold "KULKARNI - 12" label | "Fictional data. This clip would tell a stranger a name and a flat number. Which tools know that?" |
| 0:15-0:35 | Baseline detector table: face/plate/phone/document -> 0/4 leaks on held-out clips | "A fixed list of classes found none of four planted leaks." |
| 0:35-1:05 | Discover: Spark concepts with "why identifying" text | "Muse Spark reads this video and proposes what identifies this creator, with a reason." |
| 1:05-1:35 | Overlay: SAM 3.1 masks following the banner and label | "SAM 3.1 tracks each through the video." |
| 1:35-1:55 | **Abstention case:** verify.json shows the code-editor mask REJECTED (OCR read code, not KULKARNI) | "SAM grounded one prompt on the wrong object. Code caught it with OCR. It does not claim certainty." |
| 1:55-2:15 | c3: Voice transcript with garbled digits; mute interval vs labelled span | "Voice hears the number. It gets digits wrong and our mute window is still 0.35 s too wide on a hard limit. I show it anyway." |
| 2:15-2:40 | Receipt: COVERED rows with checks, UNRESOLVED rows | "After redaction we re-check the exported file with local OCR and a face detector. Anything not cleared stays UNRESOLVED. Never 'safe'." |
| 2:40-3:00 | `gate/GATE_RESULT.md` FAIL table, then post-gate table | "Our own pre-registered gate failed. Here is what I fixed after seeing it, labelled as such, and what is still failing. Veil: models propose, code decides." |
