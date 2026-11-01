# Veil demo video: outputs

| File | What |
|---|---|
| `veil-demo-web.mp4` | 1920x1080, 30 fps, H.264 CRF 18, AAC 320k, 2:17, -16.0 LUFS / -4.0 dBTP. **Upload this one.** |
| `veil-demo-social.mp4` | same video, -14.0 LUFS / -2.0 dBTP |
| `veil-demo.srt`, `veil-demo.vtt` | 56 caption cues from the script, timed to the voiceover |
| `poster.png` | thumbnail (0:46, input regions vs covered output) |
| `veil-draft.mp4` | raw Remotion render before the final loudness pass |

## Real vs recreated
- **Real:** every UI shot is a Playwright recording (real Chrome) of the redesigned Veil site (`veil/web`, deployed at thecodekaizen.github.io/veil) showing real pipeline artifacts from end-to-end repeat r1 (`runs-rep/r1/c2`, `runs-rep/r1/c3`). The gate table and ledger shots are the live site's own sections. Spark callout quotes are verbatim `why_identifying` model outputs. Stat and gate numbers come from `eval/results/final/heldout_results.md`, `gate/GATE_RESULT.md` and `gate/postgate*/GATE_RESULT.md`. Terminal lines are verbatim output of a live run (`live-smoke1`, 2026-11-01), shortened to 5 lines.
- **Typeset (not screen captures):** the hook boxes (label geometry), the triptych crops and waveform (real clip frames and c3 audio), the stat cards and the gate table.
- **Voice:** AI narration with Kokoro-82M (Apache-2.0, voice `am_michael`), chosen by the author over a clone of his own voice. Disclosed on the end card.
- **Footage licence:** street footage by Subhashish Panigrahi and Fowler&fowler, Wikimedia Commons, CC BY-SA 3.0, so this video is a CC BY-SA 3.0 derivative. Credit is on the end card.

## QA (`./qa.sh out/veil-draft.mp4`)
Duration 136.9 s (< 3:00); no black frames; one silence of 1.6 s (end-card tail); final-audio WER vs script 6.5% by Whisper (numbers written as digits).
Most misses are "Muse", which Whisper consistently mishears on the cloned voice. **Listen before uploading.** No music (none provided); `mix.sh` ducks a track automatically if `demo/audio/music.*` exists.

## Re-render
```sh
cd demo
.venv/bin/python process_voice.py        # clean, check, stitch VO -> voice/vo.wav, timing/
.venv/bin/python build_timeline.py       # -> video/src/data/timeline.json
cp voice/vo.wav video/public/vo.wav
(cd video && npx remotion render Veil ../out/veil-draft.mp4 --codec=h264 --crf=18)
./mix.sh out/veil-draft.mp4              # loudness versions (+ music if present)
./qa.sh out/veil-demo-web.mp4
```

## v3 additions
- Impact card: exposure times measured from the r1 c2 track spans (name 23.3 s, flat number 22.3 s of 25 s).
- Natural export beat: real `veil naturalize` output on r1 c2 (audit COVERED, 0 original words in 53 OCR'd frames).
- Open-weight beat: real Muse Glimmer proposals from `runs-glimmer/c2s` (5/9 keyframes answered; c2: 2/2 leaks, control not flagged).
