# API notes

Tags: **observed** = saved real response in the repo; **documented** = official docs (fetched 2026-11-01), not exercised here.
Earlier observations (SAM video, Spark hosted, Voice file mode) are in `veil/docs/MODEL_CAPABILITIES.md` with artifacts under `veil/artifacts/smoke-001/`.

## Muse Spark Open on Baseten (`meta-models/muse-spark-open-1026`)
**Not tested.** No Baseten key is present (checked `.env` and the environment by name only). Needed for the open-weight bonus.
Open questions: endpoint/base URL, request shape (chat-completions with image?), JSON-mode support, latency. Paste Baseten's chat-completions doc + `BASETEN_API_KEY` to run this.

## Voice Transcribe (`muse-voice-transcribe-1.0`) — smoke test 2026-11-01
Script: `veil/scripts/voice_timing_smoke.py`. Raw responses: `veil/artifacts/voice-timing-001/`.
Input: synthetic 18 s mono 24 kHz English audio (macOS TTS, fictional number 202-555-0146). **n = 1 clip, English only; no Hindi/Hinglish audio tested.**

### Timing
| Mode | Timing granularity | Verdict |
| --- | --- | --- |
| Word/token timestamps, any mode | none (documented: unavailable in every mode; response fields observed: `sessionId, transcript, audioDurationMs, turns[turnId,startMs,endMs,transcript]`) | observed + documented |
| Realtime WebSocket `wss://api.meta.ai/v1/asr/realtime` | documented events carry only `audioProcessedMs`; not exercised | documented, unobserved |
| File endpoint with `Accept: text/event-stream` (SSE) | events: `audioProgress` (every 80 ms), `transcript` partials, `speechStart/End/Complete`. Only timing field is `audioProcessedMs` (processing progress, lags speech: "The" emitted at 3840 ms, true onset 3000 ms). **Observed: the digit turn never appeared; final transcript empty.** | observed — not usable as timing source |
| ENDPOINTING turns (file) | turn start/end only: `[2540, 8060]` then `[8780, 8940]` vs energy-based spoken span of the number ≈ 4.9–9.15 s. Turn 0 ended mid-number; start 0.5 s early | observed — too coarse, can cut the number |
| **Windowed** (2.0 s windows, 0.5 s overlap, `PUSH_TO_TALK`, keywords on; 12 requests, ~1.6–2.3 s each) | hit windows 2–5 → number localized to **[3.0, 9.5] s** (window precision 2 s). Pseudo-truth span from local energy segmentation [4.9, 9.15]. Covers 100% of it; over-cover ≈ 1.9 s early + 0.35 s late = **2.25 s** (before any bleep padding; ±150 ms pad would give ≈ 2.55 s, over the 2.5 s G4b limit) | observed — only method that covered the whole number |

Pseudo-truth is model-free energy segmentation (threshold 0.02 RMS), not a hand label; real labels come from the gate labeller.
Window transcripts: w2 "…is two", w3 "number is two zero two", w4 "five five five zero", w5 "zero one four six" → stitched digits depend on de-duplicating the overlap (the "zero" at the w4/w5 boundary is ambiguous).

### Keyword biasing (`keywords` array in the `request` part; documented as bias only, no spelling guarantee)
Truth digits: `2025550146`. Digits scored after converting spelled-out words.
| Request | Transcript form | Digits | Exact |
| --- | --- | --- | --- |
| baseline (`languageBias:[English]`) | "…number is 2145550146" | 2145550146 | no (2 digits wrong) |
| + keywords (`phone number`, zero…nine) | "…is two zero two five five five zero one four six" | 2025550146 | **yes** |
| `languageBias:[English,Hindi]` | "…2145550146", duplicated word "demonstration" | 2145550146 | no |
| `[English,Hindi]` + keywords | "…is two zero two … four six six" | 20255501466 | no (extra digit) |
Takeaway (n = 1 per row, not statistically meaningful): keywords made the model spell digits as words (a validator must accept word digits) and improved this one clip; adding Hindi bias hurt it. Digit accuracy remains a reported metric, not a gate.
The earlier smoke-001 run (no keywords) read the number as `55460146`; baseline here read `2145550146` — the same audio gives different errors across calls (nondeterministic).

### Other
- File latency 4.2–6.5 s for 18 s audio; windows ~1.6–2.3 s each. Cost ≈ $0.18 / audio hour → this test ≈ $0.002 (estimate).
- `languageBias` accepts language names (documented list of 25 incl. Hindi, Marathi, English). "Hinglish" is not a listed value; code-switching is documented but untested.
- `keywords` and `languageBias` are set per request; cannot change mid-session (documented).

## Decision input for G4 (see gate/GATE.md)
Detection (a phone-like run of ≥ 6 digits from ≥ 4 consecutive digit tokens) is feasible with keywords + word-digit normalization. Localization needs windowed transcription; turn-level timing alone failed to cover the number.
