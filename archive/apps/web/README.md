# SHOWME web app

The Next.js App Router client provides the three SHOWME surfaces—**Teach, Do, Simulate**—over one shared Skill Model.

## Run the local API

From the repository root, install dependencies and start the local API:

```sh
python3 -m venv backend/.venv
backend/.venv/bin/pip install -e 'backend[api,meta]'
PYTHONPATH=backend backend/.venv/bin/uvicorn showme.api:app --reload --port 8000
```

Set `MODEL_API_KEY` in the ignored repository `.env` file or API process environment. Keep it server-side; never expose it to the browser or commit it. Model calls may use Meta API credits.

## Run this app

In another terminal:

```sh
cd apps/web
npm install
npm run dev
```

Open `http://localhost:3000`. The API defaults to `http://localhost:8000`; override it with `NEXT_PUBLIC_SHOWME_API_URL` if needed.

## Honest capability boundaries

- Teach returns a model-generated candidate that needs human review.
- Do supports local learner-clip recording or upload, local clip download, explicit snapshot checks, and a separate clip comparison request. It is not continuous tracking.
- Simulate replays a reordered action sequence against the Skill Model. It is a procedural state preview, not physics.
- See the root [README](../../README.md) for current screenshots and the locked product definition.
