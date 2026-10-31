"""Loopback reference API. Cloud operations require explicit per-request authorization."""
import os
from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile
from typing import Literal
from veil.core.models import StrictModel
from veil.core.pipeline import MetaPipeline
from fastapi.responses import FileResponse
from veil.core.jobs import JobStore, Conflict
from veil.core.models import Timeline
from veil.core.natural import NaturalRequest


class CloudRequest(StrictModel):
    allow_cloud_transfer: Literal[True]
    media_is_synthetic_or_consented: Literal[True]
    seed_omit_phone: bool = False
    face_action: Literal['cover','blur'] = 'cover'


def create_app(root: Path | None = None, pipeline=None):
    app = FastAPI(title='VEIL', version='0.4.0', description='Bounded Meta detection, redaction, sampled exported-media audit and repair. No zero-leak guarantee.')
    store = JobStore(root or Path(os.getenv('VEIL_JOBS_DIR', 'artifacts/private/jobs')), pipeline or MetaPipeline(os.getenv('VEIL_ENV_FILE', '.env'),max_calls=int(os.getenv('VEIL_MAX_MODEL_CALLS','12'))))
    app.state.store = store

    @app.exception_handler(FileNotFoundError)
    async def missing(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=404, content={'detail': 'Unknown job or artifact'})

    @app.exception_handler(Conflict)
    async def conflict(request, exc):
        from fastapi.responses import JSONResponse
        return JSONResponse(status_code=409, content={'detail': str(exc)})

    @app.post('/v1/jobs', status_code=201)
    def create_job(video: UploadFile):
        try:
            return store.create(video.file)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc
        finally:
            video.file.close()

    @app.get('/v1/jobs/{job_id}')
    def get_job(job_id: str):
        return store.get(job_id)

    @app.post('/v1/jobs/{job_id}/redact')
    def redact_job(job_id: str, timeline: Timeline | None = None):
        try:
            return store.redact(job_id, timeline)
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.post('/v1/jobs/{job_id}/natural')
    def natural_job(job_id: str, request: NaturalRequest):
        try:
            return store.natural(job_id,request)
        except ValueError as exc:
            raise HTTPException(422,str(exc)) from exc

    @app.get('/v1/jobs/{job_id}/natural-review')
    def natural_review(job_id: str):
        return store.natural_review(job_id)

    @app.get('/v1/jobs/{job_id}/findings')
    def findings(job_id: str):
        import json
        directory = store.directory(job_id)
        path = directory / 'timeline.json'
        return {'detection': store.get(job_id)['detection'], 'source': 'job_timeline',
                'timeline': json.loads(path.read_text()) if path.exists() else None}

    @app.get('/v1/jobs/{job_id}/receipt')
    def receipt(job_id: str):
        import json
        directory = store.directory(job_id)
        if store.get(job_id)['status'] != 'rendered':
            raise Conflict('Export is not ready')
        return json.loads((directory / 'receipt.json').read_text())

    @app.get('/v1/jobs/{job_id}/export')
    def export(job_id: str):
        directory = store.directory(job_id)
        job=store.get(job_id)
        if job['status'] != 'rendered':
            raise Conflict('Export is not ready')
        if 'natural_verification' in job:
            review=store.natural_review(job_id)
            if review.get('status')!='original_identifier_check_completed_visual_review_required':
                raise Conflict('Natural export audit is missing, stale or incomplete; create a fresh reviewed job')
            if job['verification']=='residual_observed':
                raise Conflict('Broad output audit observed an exposure; export requires repair and a fresh natural review')
        return FileResponse(directory / 'export.mp4', media_type='video/mp4', filename='veil-redacted.mp4')

    @app.post('/v1/jobs/{job_id}/detect')
    def detect(job_id: str, request: CloudRequest):
        return cloud(job_id, 'detect', request)

    @app.post('/v1/jobs/{job_id}/verify')
    def verify(job_id: str, request: CloudRequest):
        return cloud(job_id, 'verify', request)

    @app.post('/v1/jobs/{job_id}/repair')
    def repair(job_id: str, request: CloudRequest):
        return cloud(job_id, 'repair', request)

    def cloud(job_id, action, request):
        if (request.seed_omit_phone or request.face_action!='cover') and action != 'detect':
            raise HTTPException(422, 'Detection-only options cannot be supplied for audit or repair')
        try:
            return store.cloud_action(job_id, action, seed_omit_phone=request.seed_omit_phone,face_action=request.face_action)
        except (Conflict, FileNotFoundError):
            raise
        except Exception as exc:
            # Provider errors can contain private response content: keep public errors generic.
            raise HTTPException(502, 'Processing failed; inspect the local job and call ledger. No automatic retry.') from exc

    @app.get('/v1/jobs/{job_id}/verification')
    def verification(job_id: str):
        import json
        directory = store.directory(job_id)
        job = store.get(job_id)
        if job['verification'] == 'not_run':
            return {'status':'not_run','revision':job.get('revision',0)}
        return json.loads((directory/'verification.json').read_text())

    return app
