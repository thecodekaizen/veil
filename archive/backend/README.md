# Backend experiments

The new `showme` package is the active hackathon direction. The earlier
`thread_engine` remains available as legacy research; do not extend it for
SHOWME features.

## SHOWME local app API

The Teach surface can send an explicitly selected video to this local service
for one Meta Model API inference. The upload is staged in a temporary directory,
converted to a bounded silent MP4, and deleted locally when the request ends.
The Meta adapter also attempts to delete its uploaded provider file. A returned
process is a candidate that needs human review; one observed trace does not
establish required dependencies.

```bash
backend/.venv/bin/pip install -e 'backend[api,meta]'
PYTHONPATH=backend backend/.venv/bin/uvicorn showme.api:app --reload --port 8000
```

The browser only calls `/api/skills/learn` after the user presses **Learn this
skill**. That call may use Meta API credits. The local `.env` file is read by
the backend and is never sent to the browser. After reviewing and loading a
candidate, the Do surface can call `/api/skills/observe` with a separate learner
clip. The model sees the reviewed process and learner video, never evaluation
labels; the response is validated for timestamps, declared states/objects, and
recovery evidence before it is shown.

Do also provides an explicit **Check current state** button while the camera is
on. That sends exactly one downscaled JPEG frame to `/api/skills/observe-snapshot`
as an inline image input to Muse Spark. It is a user-triggered snapshot check,
not continuous tracking. The API stages the JPEG in a temporary directory,
discards it after the request, and validates returned IDs against the reviewed
process. A still image cannot establish action order or recovery. Each click may
use API credits; no snapshot inference runs in the background.

For a local HoloAssist scoring pass:

```bash
showme score-holoassist path/to/annotation.json path/to/observation.json
```

The annotation file is read only by the local evaluator and is never passed to
Muse. By default, a divergence timestamp must fall within a human-labeled
wrong-action interval; `--tolerance SECONDS` adds an explicit margin. The
report counts one hit per labeled interval and includes precision, recall,
misses, and false-alert timestamps. This scores event timing only, not the
semantic correctness of the claimed error or recovery quality.

## Prepare local video

```bash
PYTHONPATH=backend backend/.venv/bin/python -m showme prepare-video path/to/clip.mp4
```

This uses `ffprobe` and `ffmpeg` locally. It writes a manifest and timestamped
JPEG frames under `.showme-runs/`; the source is not modified or uploaded.

## Learn from one demonstration

Install the optional SDK once with `pip install -e 'backend[meta]'`, then run:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m showme learn-video path/to/demo.mp4
```

This uploads one MP4 to the Meta Model API, asks Muse Spark for a structured
candidate process, records token usage, requests one-hour file expiry, and tries
to delete the uploaded file after inference. The local run directory is ignored
by Git. A model response is a hypothesis, not ground truth; check its timestamped
evidence before using it for learner-state evaluation. The cross-reference
validator is an intentional first learning exercise and currently reports as
pending until implemented.

## Compare a learner attempt

After reviewing the learned process artifact, compare one neutral-named learner
clip against it:

```bash
PYTHONPATH=backend backend/.venv/bin/python -m showme observe-video \
  .showme-runs/learned/your-run/process.json path/to/learner.mp4
```

The observer receives the learned process and one video. It never receives the
human evaluation key. It writes timestamped events and divergence evidence to
`.showme-runs/observed/`; local validation rejects unknown state/object IDs,
invalid timestamps, and unsupported recovery claims. A passing validator only
means the response is structurally grounded in the process IDs and clip time; it
does not prove the model understood the physical task.
