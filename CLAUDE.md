# Veil — project rules for Claude Code

## What Veil is
An open-vocabulary privacy-risk audit for creator videos, built solo for the Meta Global AI
Developer Hackathon (Indie track). Building period: Oct 27 – Nov 4, 2026.
- Muse Spark proposes what in THIS specific video could identify the creator.
- SAM 3.1 tracks those things through the video.
- Muse Voice Transcribe hears spoken identifiers (Hindi / English / Hinglish).
- Deterministic code redacts, re-checks the OUTPUT with independent detectors, and reports
  what is COVERED, UNRESOLVED, or NOT_CHECKED.

## Non-negotiable principles
1. Models propose; code decides. A model output is a candidate, never a fact. Every status in
   the final report is computed by code from stored artifacts.
2. Abstain loudly. The only finding statuses are COVERED, UNRESOLVED, NOT_CHECKED.
   Never output or display "safe", "certified", "guaranteed", "100% private", "leak-free".
   The report may say "no unresolved risks found by the checks listed" and must list the checks.
3. Every stage writes runs/{run_id}/{stage}.json, validated by a pydantic model in
   veil/schemas.py. Stages read only artifacts, never each other's in-memory state.
   Re-running a stage is idempotent.
4. Never guess an external API's request/response shape. Shapes live in docs/api_notes.md,
   recorded from real smoke-test responses. If a shape is unknown: stop and ask me for docs.
5. No real personal data anywhere: fixtures, tests, demo clips, watchlists. Use obviously
   fictional values (e.g. name "Rohan Kulkarni", phone 98765 43210, "Flat 12, Sunshine CHS,
   Fakepur 400099"). Keep them in config/fictional_allowlist.json. Footage must be synthetic,
   staged, or explicitly consented; document every cloud transfer of media to Meta.
6. New-work rule: everything here is built during the hackathon (from Oct 27, 2026). Anything
   copied from an older repo goes under vendor/ with a header comment stating origin + original
   date, and is listed in README under "Pre-existing code". Never rewrite git history.
7. Secrets only in .env (gitignored). Never print keys or full request headers in logs.
   No employer code/data/IP in the repo.
8. Never claim zero leaks, or "fully local" processing while cloud models are used. Same-model
   output review is not independent evidence; say so where it applies.
9. Ground truth / answer keys are evaluation-only and never enter inference.
10. Record failures, actual model calls, latency and estimated cost; no hidden retries,
    fabricated detections, mocks presented as inference success, or invented metrics.

## Stack
Python 3.12, uv, FastAPI, pydantic v2 (+ pydantic-settings), httpx, numpy,
opencv-python-headless, ffmpeg (system binary), pytest, ruff.
Frontend: React + Vite + TypeScript. Container: Docker. Deploy: Cloud Run.
Encode H.264 with -preset veryfast unless told otherwise.

## Layout
veil/            config.py, schemas.py, cli.py
veil/clients/    meta_spark.py, meta_sam.py, meta_voice.py, baseten_spark_open.py
veil/stages/     ingest.py, discover.py, track.py, listen.py, redact.py, audit.py, report.py
veil/validators/ spoken_digits.py, pii.py
veil/prompts/    versioned prompt text files (discover_v1.txt, narrate_v1.txt)
gate/            GATE.md, labels/*.json, score_gate.py, clips/ (gitignored)
eval/            manifest.yaml, run_eval.py, results/
server/          FastAPI app
web/             React app
runs/            gitignored, except runs/demo/ (committed precomputed demo output)
docs/            api_notes.md, decisions.md, plan.md, demo_script.md

## Commands
make setup | make test | make gate | make eval | make serve | make web
uv run veil run CLIP.mp4 --run-id ID [--stages ingest,discover,track,listen,redact,audit,report]

## Working style
- Small commits, conventional messages, one concern each.
- Write the pydantic schema and a failing test before the implementation.
- Log every model call to runs/{id}/calls.jsonl: model id, endpoint, latency_ms,
  input size, status, error (no secrets).
- No network calls in unit tests; use recorded fixtures from docs/smoke/.
- When a task is done, report: what changed, how you verified it (exact command + output
  summary), what is still unverified.
- Preserve unrelated uncommitted work. Explain important engineering decisions briefly; don't
  block authorized work with learning checkpoints or repeated approval prompts.
- Test and inspect generated media (decode frames, check audio), don't trust metadata alone.

## Environment and existing code
- Python 3.12. The API key env var is `MODEL_API_KEY` (not META_API_KEY); use it in `.env.example`.
- The repo is public. Never commit media or text of unknown consent or license; `real-driving-1080p.mp4`
  is gitignored. Superseded THREAD/SHOWME prototypes live in `archive/` and are not part of the submission.
- The existing engine is in `veil/src/veil/...` with tests in `veil/tests`; the Layout above is the target
  and will be adapted to the real structure (decision pending). See docs/decisions.md.
- Local OCR in the existing engine is macOS-only (Swift/Vision); the Cloud Run build needs a portable OCR.
