# Script: Veil (2:30 judge cut)

Words: **318** (budget 325 ±10% = 292–358). Est. read time at 150 wpm incl. pauses: **145 s**.

| Beat | words | est. s |
|---|---|---|
| Hook | 19 | 7.6 |
| Contrast | 17 | 6.8 |
| One line | 21 | 8.4 |
| Natural | 36 | 14.4 |
| Live | 11 | 4.4 |
| Find | 22 | 8.8 |
| Listen | 24 | 9.6 |
| Audit | 28 | 11.2 |
| Proof | 70 | 28.0 |
| Models | 29 | 11.6 |
| Open weights | 22 | 8.8 |
| Close | 19 | 7.6 |

| id | VO | On screen | Emphasis | Pause | Evidence |
|---|---|---|---|---|---|
| h1 | This street clip is about to be posted. | c2 playing; About to be posted. | about to be posted | 250 ms | `runs-rep/r1/c2 input` |
| h2 | It shows a stranger my full name, and my flat number. | amber boxes on the notification and door plate | full name, flat number | 400 ms | `runs-rep/r1/c2 redact.json boxes` |
| x1 | A standard redaction tool looks for faces and plates. It covers one car's plate, and misses both. | real standard-class export of the same run | faces and plates, one car's plate, misses both | 600 ms | `runs-rep/r1/c2/output_fixed_classes.mp4` |
| o1 | Veil finds what identifies you in this specific video. Not just faces and plates. Then it covers it, before you post. | Veil wordmark; side by side standard vs Veil | this specific video, covers it | 1500 ms | `runs-rep/r1/c2 output.mp4` |
| nx | Or skip the black boxes. Natural mode swaps in a fictional name, in the same style, so the video still looks real. | c2demo input vs natural export, wipe | skip the black boxes, fictional name, still looks real | 500 ms | `runs/c2demo natural.json, output_natural.mp4` |
| ex | And on a still photo, Muse Image erases it, and rebuilds what was behind. | still: input vs Muse Image erase | Muse Image erases it | 1300 ms | `docs/media/erase/erase.json, calls.json` |
| l1 | Here's the live product. Drag across, and see exactly what changed. | live site hero: divider dragged across input vs export | live product | 500 ms | `thecodekaizen.github.io/veil` |
| a2 | Muse Spark reads the clip, and proposes what could identify you, with a reason. | desk: Spark boxes + verbatim reason | Muse Spark, with a reason | 1700 ms | `runs-rep/r1/c2 discover.json` |
| a3 | SAM 3.1 tracks each one, through every frame. | desk tracks panel | SAM 3.1, every frame | 1300 ms | `runs-rep/r1/c2 track_final.json` |
| v1 | It listens, too. Muse Voice hears a phone number said in Hindi, and Veil mutes it. | desk c3: transcript, mute bar | Hindi, mutes it | 400 ms | `runs-rep/r1/c3 listen.json, redact.json` |
| v2 | Then it transcribes the export again, to confirm. | findings: COVERED spoken phone-like number (re-transcription found no digit run) | confirm | 1500 ms | `runs-rep/r1/c3 audit.json` |
| au | Then Veil audits its own export. | desk verdict banner | audits | 250 ms | `runs-rep/r1/c2 audit.json` |
| au2 | Ten items covered. Two left for you to review. | verdict: 10 COVERED, 2 UNRESOLVED, 0 NOT CHECKED | Five items covered, Two left | 450 ms | `runs-rep/r1/c2 audit.json` |
| r1 | Every finding ends covered, unresolved, or not checked. Never a blanket all clear. | findings, Unresolved filter | unresolved, all clear | 350 ms | `runs-rep/r1/c2 audit.json` |
| p1 | I planted four private details across three test clips. Standard detection found none. | proof card: test set; standard 0 of 4 | four private details, found none | 300 ms | `eval/results/final/heldout_results.md` |
| p2 | Over three full runs, Veil found eleven of twelve. One run missed a parcel label, and its audit didn't catch it. | stat hit: 4/4, 3/4, 4/4 cells; the miss outlined | eleven of twelve, didn't catch it | 350 ms | `gate/repeats/r1-r3; runs-rep/r2/c1 audit.json` |
| p2b | After one fix to the mask check, three new runs found all twelve. Audio timing still fails my own test. | stat hit: post-gate v2 row 12 of 12; audio caveat | all twelve, still fails | 450 ms | `gate/repeats-v2; eval/repeats-v2/summary.md` |
| p3 | Every model call is logged: seven hundred and fifty-one calls, about two dollars forty per clip. | live site ledger | logged | 450 ms | `eval/repeats/summary.json` |
| m1 | Each Meta model does one job. Muse Spark finds, SAM 3.1 tracks, Muse Voice listens, and Muse Image erases. Without Spark, the standard tool finds none of the four. | models card: role + impact per model | one job, none of the four | 700 ms | `README 'The Meta models'; eval/results/final/heldout_results.md` |
| g1 | Discovery also runs on Muse Glimmer, right on this laptop. The frames never leave it. | Glimmer card | Muse Glimmer, never leave it | 900 ms | `runs-glimmer/c2s; eval/glimmer/summary.md` |
| g2 | On this clip, it found both details. | Glimmer card result line | both details | 500 ms | `gate/glimmer; eval/glimmer/summary.md` |
| c1 | Veil. Find what identifies you, and fix it naturally, before you post. | end on the after frame, wordmark, URLs | before you post | 1300 ms | `README` |
| c2 | Try it live, at the link below. | URLs on the after frame | Try it live | 1500 ms | `thecodekaizen.github.io/veil` |

## Alternative hooks
- **B:** "Here's what a stranger learns from twenty-five seconds of my street." (on screen: findings ticking in)
- **C:** "Blurring faces isn't enough. This clip has no face problem, and it still gives me away." (on screen: baseline face/plate boxes find nothing)

## Must not say
safe (except "never says a video is safe"), certified, guaranteed, private, leak-free, any competitor name, any gate PASS without 'post-gate'.
